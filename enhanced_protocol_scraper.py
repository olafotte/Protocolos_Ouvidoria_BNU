import argparse
import asyncio
import json
import logging
import os
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm.asyncio import tqdm as asyncio_tqdm
from tqdm import tqdm

# --- Helper Functions for Filtering ---
def remover_acentos(txt):
    if not txt:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

def get_lista_normalizada(lista_original, familias):
    mapa_familias = {}
    for key, variantes in familias.items():
        for v in variantes:
            mapa_familias[remover_acentos(v).lower()] = set(remover_acentos(va).lower() for va in variantes)

    lista_normalizada = set()
    for nome in lista_original:
        nome_sem_acento = remover_acentos(nome).lower()
        if nome_sem_acento in mapa_familias:
            lista_normalizada.update(mapa_familias[nome_sem_acento])
        else:
            lista_normalizada.add(nome_sem_acento)
    return list(lista_normalizada)

def contains_any_keyword(block, keywords):
    if not block:
        return False
    block_norm = remover_acentos(block).lower()
    return any(word in block_norm for word in keywords)

def find_and_format_dates(content):
    """Finds all dd/mm/yyyy dates in a string and returns the latest one in yyyy-mm-dd format."""
    if not content:
        return None

    date_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})')
    found_dates = date_pattern.findall(content)

    if not found_dates:
        return None

    latest_date = None
    for date_str in found_dates:
        try:
            current_date = datetime.strptime(date_str, '%d/%m/%Y')
            if latest_date is None or current_date > latest_date:
                latest_date = current_date
        except ValueError:
            continue

    if latest_date:
        return latest_date.strftime('%Y-%m-%d')
    
    return None

# --- Configuration and Logging Setup ---

def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

class Config:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.settings = json.load(f)

    def __getattr__(self, name):
        return self.settings.get(name)

# --- Database Management ---

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetchall(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def init_db(self):
        logging.info("Initializing database...")
        self.execute('''
            CREATE TABLE IF NOT EXISTS protocols (
                year INTEGER,
                number INTEGER,
                content TEXT,
                Arquivado TEXT,
                Last_update TEXT,
                retrieved_at TIMESTAMP,
                PRIMARY KEY (year, number)
            )
        ''')
        logging.info("Database initialized.")

    def get_existing_protocols(self, year):
        rows = self.fetchall('SELECT number FROM protocols WHERE year = ?', (year,))
        return {row[0] for row in rows}

    def get_protocols_to_update(self, year, days=90):
        ninety_days_ago = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = self.fetchall(
            "SELECT number FROM protocols WHERE year = ? AND Arquivado = 'no' AND Last_update >= ?",
            (year, ninety_days_ago)
        )
        return {row[0] for row in rows}

    def insert_protocol(self, year, number, content, arquivado, last_update):
        self.execute(
            'INSERT OR REPLACE INTO protocols (year, number, content, Arquivado, Last_update, retrieved_at) VALUES (?, ?, ?, ?, ?, ?)',
            (year, number, content, arquivado, last_update, datetime.now())
        )

# --- Web Scraping ---

class Locators:
    IFRAME = (By.TAG_NAME, "iframe")
    EXERCICIO_INPUT = (By.ID, "form:exercicioSituacaoNumero:field")
    NUMERO_INPUT = (By.ID, "form:numeroSituacaoNumero:field")
    TIPO_PROTOCOLO_DROPDOWN = (By.ID, "form:tipoProtocoloSituacaoNumero:select")
    BOTAO_LOCALIZAR = (By.ID, "form:j_id_42:0:j_id_46")
    OVERLAY_CARREGANDO = (By.CLASS_NAME, "carregandoFundo")
    RESULTADO_FIELDSET = (By.XPATH, "//span[@id='form:resultadoSituacaoNumero']/fieldset")
    RESULTADO_FIELDSET_ERRO = (By.XPATH, "//span[@id='form:resultadoSituacaoNumero']")

class ProtocolScraper:
    def __init__(self, base_url, headless=True):
        self.base_url = base_url
        self.headless = headless

    def _init_driver(self):
        service = Service(log_path=os.devnull)
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--log-level=3")
        return webdriver.Chrome(service=service, options=options)

    async def scrape_protocol(self, session, year, number):
        loop = asyncio.get_event_loop()
        try:
            content, arquivado, last_update = await loop.run_in_executor(
                None, self._perform_scrape, year, number
            )
            return year, number, content, arquivado, last_update
        except Exception as e:
            logging.error(f"Error scraping {year}/{number}: {e}")
            return year, number, f"SCRAPE_ERROR: {e}", "no", None

    def _perform_scrape(self, year, number):
        driver = self._init_driver()
        wait = WebDriverWait(driver, 10)
        driver.get(self.base_url)
        content = "Default error content."
        arquivado = "no"
        last_update = None
        try:
            wait.until(EC.presence_of_element_located(Locators.IFRAME))
            driver.switch_to.frame(driver.find_element(*Locators.IFRAME))

            wait.until(EC.presence_of_element_located(Locators.EXERCICIO_INPUT)).send_keys(str(year))
            wait.until(EC.presence_of_element_located(Locators.NUMERO_INPUT)).send_keys(str(number))
            Select(wait.until(EC.presence_of_element_located(Locators.TIPO_PROTOCOLO_DROPDOWN))).select_by_index(9)
            
            wait.until(EC.invisibility_of_element_located(Locators.OVERLAY_CARREGANDO))
            wait.until(EC.element_to_be_clickable(Locators.BOTAO_LOCALIZAR)).click()

            wait.until(EC.text_to_be_present_in_element(Locators.RESULTADO_FIELDSET, f"{year}/{number}"))
            content = driver.find_element(*Locators.RESULTADO_FIELDSET).text

            if "Conforme andamento arquiva-se o protocolo." in content:
                arquivado = "yes"
            
            last_update = find_and_format_dates(content)

        except TimeoutException:
            try:
                content = driver.find_element(*Locators.RESULTADO_FIELDSET_ERRO).text
            except NoSuchElementException:
                content = "Timeout: Protocol not found or page did not load."
        except Exception as e:
            content = f"An unexpected error occurred: {e}"
        finally:
            driver.quit()
        return content, arquivado, last_update

    def _check_protocol_exists(self, driver, wait, year, number):
        """A dedicated method for the binary search to check if a protocol exists."""
        try:
            # This is slow, but safer than trying to navigate 'back' on a complex JS page
            driver.get(self.base_url)
            
            wait.until(EC.presence_of_element_located(Locators.IFRAME))
            driver.switch_to.frame(driver.find_element(*Locators.IFRAME))

            wait.until(EC.presence_of_element_located(Locators.EXERCICIO_INPUT)).send_keys(str(year))
            wait.until(EC.presence_of_element_located(Locators.NUMERO_INPUT)).send_keys(str(number))
            Select(wait.until(EC.presence_of_element_located(Locators.TIPO_PROTOCOLO_DROPDOWN))).select_by_index(9)
            
            wait.until(EC.invisibility_of_element_located(Locators.OVERLAY_CARREGANDO))
            wait.until(EC.element_to_be_clickable(Locators.BOTAO_LOCALIZAR)).click()

            # A short wait for the result. A successful result should contain the protocol number.
            # If it times out, we'll check for the error message.
            WebDriverWait(driver, 5).until(
                EC.text_to_be_present_in_element(Locators.RESULTADO_FIELDSET, f"{year}/{number}")
            )
            # If the above line doesn't time out, the protocol exists.
            return True
        except TimeoutException:
            # The success text didn't appear. Check for the explicit "not found" message.
            try:
                error_text = driver.find_element(*Locators.RESULTADO_FIELDSET_ERRO).text
                if "Protocolo não localizado" in error_text:
                    return False # Explicitly not found
            except NoSuchElementException:
                # If we can't even find the error container, it's definitely not found.
                return False
            # If we find the container but not the specific message, or something else goes wrong,
            # it's safer to assume it's not found.
            return False
        except Exception as e:
            logging.warning(f"An error occurred in _check_protocol_exists for {year}/{number}: {e}")
            # Any other exception means we can't be sure, so assume it doesn't exist.
            return False

    def find_latest_protocol_number(self, year):
        logging.info(f"Starting binary search for the latest protocol in {year}.")
        driver = self._init_driver()
        # Use a longer wait for general navigation, but the check method uses a shorter one.
        wait = WebDriverWait(driver, 10) 
        low, high = 1, 30000
        latest_found = 0

        try:
            with tqdm(total=high, desc=f"Binary searching in {year}") as pbar:
                # Adjust the range to avoid testing 0 and to have a more realistic start
                if low == 0: low = 1

                while low <= high:
                    mid = (low + high) // 2
                    if mid == 0: # Skip protocol 0
                        low = 1
                        continue

                    pbar.set_description(f"Testing {mid}")
                    
                    if self._check_protocol_exists(driver, wait, year, mid):
                        # Found one, it could be the latest. Try for a higher number.
                        latest_found = mid
                        low = mid + 1
                    else:
                        # Not found, the latest must be in the lower half.
                        high = mid - 1
                    
                    # Update progress bar
                    pbar.n = latest_found
                    pbar.refresh()
        finally:
            driver.quit()
        
        logging.info(f"Found latest protocol for {year}: {latest_found}")
        return latest_found

# --- Main Application Logic ---

async def main():
    config = Config()
    setup_logging(config.log_file)

    parser = argparse.ArgumentParser(description="Protocol Scraper and Analyzer.")
    parser.add_argument('action', choices=['init_db', 'scrape', 'analyze'], help='Action to perform.')
    parser.add_argument('--year', type=int, help='Year to process.')
    parser.add_argument('--force-update', action='store_true', help='Force update of all protocols for the year.')
    parser.add_argument('--no-headless', action='store_true', help='Run browser in non-headless mode.')
    args = parser.parse_args()

    # Load keyword filters from config
    lista_original = config.settings.get('lista_original', [])
    familias = config.settings.get('familias', {})
    LISTA_NORMALIZADA = get_lista_normalizada(lista_original, familias)

    with DatabaseManager(config.database_name) as db:
        if args.action == 'init_db':
            db.init_db()

        elif args.action == 'scrape':
            scraper = ProtocolScraper(config.base_url, headless=not args.no_headless)
            years_to_process = [args.year] if args.year else config.hardcoded_years.keys()
            
            all_newly_scraped = defaultdict(list)

            for year in years_to_process:
                year = int(year)
                logging.info(f"--- Processing year: {year} ---")
                
                if str(year) == str(config.current_year):
                    max_num = scraper.find_latest_protocol_number(year)
                else:
                    max_num = config.hardcoded_years.get(str(year))

                if not max_num:
                    logging.error(f"Could not determine max protocol number for {year}.")
                    continue

                all_protocols = set(range(1, max_num + 1))
                
                if args.force_update:
                    protocols_to_scrape = sorted(list(all_protocols))
                else:
                    existing_protocols = db.get_existing_protocols(year)
                    new_protocols = all_protocols - existing_protocols
                    protocols_to_update = db.get_protocols_to_update(year,60)
                    protocols_to_scrape = sorted(list(new_protocols.union(protocols_to_update)))


                if not protocols_to_scrape:
                    logging.info(f"No new or unarchived protocols to scrape for {year}.")
                    continue

                logging.info(f"Found {len(protocols_to_scrape)} protocols to scrape for {year}.")
                all_newly_scraped[year] = protocols_to_scrape
                
                tasks = []
                sem = asyncio.Semaphore(config.max_concurrent_tasks)
                async def scrape_with_sem(protocol_number):
                    async with sem:
                        return await scraper.scrape_protocol(None, year, protocol_number)

                for number in protocols_to_scrape:
                    tasks.append(scrape_with_sem(number))

                for future in asyncio_tqdm.as_completed(tasks, total=len(tasks), desc=f"Scraping {year}"):
                    res_year, res_number, res_content, res_arquivado, res_last_update = await future
                    if not res_last_update:
                        res_last_update = datetime.now().strftime('%Y-%m-%d')
                    db.insert_protocol(res_year, res_number, res_content, res_arquivado, res_last_update)
            
            # --- Analyze newly scraped protocols and generate Update.txt ---
            logging.info("Analyzing newly scraped protocols for keyword matches...")
            new_matching_protocols = []
            
            for year, numbers in all_newly_scraped.items():
                for number in numbers:
                    cursor = db.execute("SELECT content FROM protocols WHERE year = ? AND number = ?", (year, number))
                    row = cursor.fetchone()
                    if not row or not row[0]:
                        continue
                    
                    content = row[0]
                    if contains_any_keyword(content, LISTA_NORMALIZADA):
                        protocol_id = f"{year}/{str(number).zfill(5)}"
                        new_matching_protocols.append({'id': protocol_id, 'content': content})

            if new_matching_protocols:
                logging.info(f"Found {len(new_matching_protocols)} new matching protocols. Generating Update.txt.")
                with open('Update.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Update de {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n\n")
                    f.write(f"Foram encontrados {len(new_matching_protocols)} novos protocolos de interesse:\n\n")
                    for proto in new_matching_protocols:
                        f.write(f"--- {proto['id']} ---\n")
                        f.write(f"{proto['content']}\n\n")
            else:
                logging.info("No new matching protocols found. Generating empty Update.txt.")
                with open('Update.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Sem update. {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
            
            logging.info("Update.txt generated.")

        elif args.action == 'analyze':
            logging.info("--- Analyzing Protocol Gaps ---")
            years = [args.year] if args.year else list(config.hardcoded_years.keys()) + [config.current_year]
            for year in years:
                year = int(year)
                rows = db.fetchall('SELECT number FROM protocols WHERE year = ? ORDER BY number', (year,))
                if not rows:
                    logging.warning(f"No data for year {year} to analyze.")
                    continue
                
                numbers = {row[0] for row in rows}
                first, last = min(numbers), max(numbers)
                missing = set(range(first, last + 1)) - numbers

                logging.info(f"Year {year}: Found {len(numbers)} protocols (from {first} to {last}).")
                if missing:
                    logging.warning(f"  - Missing {len(missing)} protocols. Examples: {sorted(list(missing))[:10]}")
                else:
                    logging.info("  - No protocols missing in the sequence.")

if __name__ == "__main__":
    asyncio.run(main())