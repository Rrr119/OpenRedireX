
<h1 align="center">
    OpenRedireX
  <br>
</h1>

<h4 align="center">A fuzzer for detecting open redirect vulnerabilities</h4>


<p align="center">
  <a href="#install">🏗️ Install</a>  
  <a href="#usage">⛏️ Usage</a>  
  <a href="#dependencies">📚 Dependencies</a>
  <br>
</p>

![OpenRedirex](https://github.com/devanshbatham/OpenRedireX/blob/master/static/openredirex.png?raw=true)

# Install

```sh
git clone https://github.com/devanshbatham/openredirex
cd openredirex
sudo chmod +x setup.sh
./setup.sh
```

# Usage

The script is executed from the command line and has the following usage options:

```sh
openredirex [-p payloads] [-k keyword] [-c concurrency] [--variants]
```

- `-p`, `--payloads`: File containing a list of payloads. If not specified, a hardcoded list is used.
- `-k`, `--keyword`: Keyword in URLs to replace with payload. Default is "FUZZ".
- `-c`, `--concurrency`: Number of concurrent HTTP requests. Default is 100.
- `-V`, `--variants`: Generate deterministic encoded and bypass variants for every base payload while removing duplicates.

The script expects a list of URLs as input. Each URL should contain the keyword specified by the `-k` option. The script replaces the keyword with each of the payloads, and attempts to fetch the modified URL. 

Example usage:

```sh
cat list_of_urls.txt |  openredirex -p payloads.txt -k "FUZZ" -c 50
```

For broader batch coverage, enable payload variants:

```sh
cat list_of_urls.txt | openredirex -p payloads.txt --variants -c 50
```

Generated variants preserve the original payloads and add common redirect bypasses, including:

- full, slash-safe, and partial URL encoding
- `http://`, protocol-relative, `:/`, and extra leading-slash forms
- backslash substitutions
- null-byte, CRLF, query, fragment, and trailing-slash suffixes


List of URLs should look like below:


```
cat list_of_urls.txt

https://newsroom.example.com/logout?redirect=FUZZ
https://auth.example.com/auth/realms/sonatype/protocol/openid-connect/logout?redirect_uri=test
https://exmaple.com/php?test=baz&foo=bar
```

This example reads URLs from the file `list_of_urls.txt`, replaces all the values of the parameters to `FUZZ` (or the supplied keyword), then replaces that keyword with each payload. The scanner uses a bounded request queue, so the value passed to `--concurrency` limits the number of HTTP requests in flight rather than only limiting the number of input URLs.



# Dependencies

The script uses the following libraries:

- `argparse` for handling command-line arguments.
- `aiohttp` for making HTTP requests.
- `tqdm` for displaying progress.
- `asyncio` for managing asynchronous tasks.

You need to install these dependencies before running the script. Most of them are part of the standard Python library. You can install `aiohttp` and `tqdm` using pip:

```sh
pip install aiohttp tqdm
```

You can use this script to check for open redirects in web applications. However, you should only use it on systems that you have been given explicit permission to test.
