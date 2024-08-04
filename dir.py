import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def logo():
    art = """
////////////////////////////////////////////////////////////
// ##  ##  #  ###     ##  ### ##  ###  ## ###  #  ##  # # //
//#   #   # # # #     # #  #  # # #   #    #  # # # # # # //
// #  #   ### # # ### # #  #  ##  ##  #    #  # # ##   #  //
//  # #   # # # #     # #  #  # # #   #    #  # # # #  #  //
//##   ## # # # #     ##  ### # # ###  ##  #   #  # #  #  //
////////////////////////////////////////////////////////////
    """
    creator = "Created by Coder Sigma"
    print(art)
    print(creator)

def color_text(text, color):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "blue": "\033[94m",
        "end": "\033[0m"
    }
    return f"{colors.get(color, colors['end'])}{text}{colors['end']}"

def load_file_list(filepaths, extension=None):
    """Load a list of file names from multiple text files and optionally append an extension."""
    encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
    file_list = []

    for filepath in filepaths:
        found_valid_encoding = False
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as file:
                    if extension:
                        file_list.extend([line.strip() + extension for line in file if line.strip()])
                    else:
                        file_list.extend([line.strip() for line in file if line.strip()])
                found_valid_encoding = True
                break
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                print(f"{color_text('[+] 404', 'red')} {filepath} not found.")
            except Exception as e:
                print(f"{color_text('[+] ERROR', 'red')} {e}")

        if not found_valid_encoding:
            print(f"{color_text('[+] ERROR', 'red')} Failed to decode {filepath} with available encodings.")

    return file_list

def load_directories(filepath):
    """Load a list of directories from a text file."""
    directories = []
    encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as file:
                directories.extend([line.strip() for line in file if line.strip()])
            break
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            print(f"{color_text('[+] 404', 'red')} {filepath} not found.")
        except Exception as e:
            print(f"{color_text('[+] ERROR', 'red')} {e}")

    return directories

def create_session():
    """Create a requests session with retry strategy."""
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def is_valid_response(response):
    """Check if the response indicates an actual existing resource."""
    if response.status_code == 200 and 'error' not in response.text.lower() and 'not found' not in response.text.lower():
        return True
    return False

def check_file(file_url, session, found_urls):
    """Check if a specific file exists at the URL and print the result."""
    try:
        response = session.get(file_url, timeout=10)
        if is_valid_response(response):
            if file_url not in found_urls:
                found_urls.add(file_url)
                print(f"{color_text('[+] FOUND', 'green')} {file_url}")
    except requests.exceptions.RequestException:
        pass

def scan_directory(directory_url, php_files, session, found_urls):
    """Scan a specific directory for files."""
    print(f"{color_text('[+] Scanning', 'blue')} {directory_url}")

    for file in php_files:
        file_url = urljoin(directory_url, file)
        if file_url not in found_urls:
            check_file(file_url, session, found_urls)

def search_site(url, base_domain, php_files, session, executor, visited_urls, found_urls):
    """Perform initial search on the site using specified file lists."""
    futures = []

    def process_url(url):
        try:
            sys.stdout.write(f"\r{color_text('[+] Searching', 'blue')} {url}")
            sys.stdout.flush()
            response = session.get(url, timeout=10)
            if not is_valid_response(response):
                return
        except requests.exceptions.RequestException as e:
            return

        if url in visited_urls:
            return
        visited_urls.add(url)

        # Check for files in the current directory
        for file in php_files:
            file_url = urljoin(url, file)
            if file_url not in found_urls:
                executor.submit(check_file, file_url, session, found_urls)

        # Find and process links in the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')

        for link in links:
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                parsed_url = urlparse(full_url)
                if parsed_url.netloc == base_domain and full_url not in visited_urls:
                    if full_url.endswith('/'):
                        future = executor.submit(process_url, full_url)
                        futures.append(future)
                    else:
                        ext = os.path.splitext(href)[1]
                        if ext in ['.php', '.aspx']:
                            if full_url not in found_urls:
                                future = executor.submit(check_file, full_url, session, found_urls)
                                futures.append(future)

    process_url(url)
    for future in as_completed(futures):
        future.result()

def scrape_directories_from_file(url, base_domain, directories, php_files, session, executor, visited_urls, found_urls):
    """Scrape directories from test.txt and check for files in them."""
    futures = []

    for directory in directories:
        directory_url = urljoin(url, directory if directory.endswith('/') else directory + '/')

        def check_and_scan(directory_url):
            try:
                response = session.get(directory_url, timeout=10)
                if is_valid_response(response):
                    print(f"\n{color_text('[+] FOUND!', 'green')} {directory_url}")
                    scan_directory(directory_url, php_files, session, found_urls)
            except requests.exceptions.RequestException as e:
                pass

        future = executor.submit(check_and_scan, directory_url)
        futures.append(future)

    for future in as_completed(futures):
        future.result()

if __name__ == "__main__":
    logo()
    parser = argparse.ArgumentParser(description='Scrape a website for specific files and directories.')
    parser.add_argument('-u', '--url', type=str, required=True, help='The URL of the directory to scrape.')

    args = parser.parse_args()
    start_url = args.url
    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc

    # Load file names and directories
    file_paths = [
        'wordlist/general/common.txt',
        'wordlist/general/admin-panels.txt'
    ]
    directories_file = 'wordlist/general/test.txt'

    php_files = load_file_list(file_paths, '.php')
    aspx_files = load_file_list(file_paths, '.aspx')
    directories = load_directories(directories_file)

    session = create_session()

    visited_urls = set()
    found_urls = set()

    with ThreadPoolExecutor(max_workers=10) as executor:
        # First perform the initial search
        search_site(start_url, base_domain, php_files, session, executor, visited_urls, found_urls)
        
        # Then process directories from test.txt
        scrape_directories_from_file(start_url, base_domain, directories, php_files, session, executor, visited_urls, found_urls)
