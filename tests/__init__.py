"""Data and utilities for testing."""
import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
from contextlib import closing

import aiohttp
import cfg4py
import omicron
import pandas as pd
from omicron.models.security import Security

cfg = cfg4py.get_instance()
logger = logging.getLogger()


def init_test_env():
    os.environ[cfg4py.envar] = "DEV"
    src_dir = os.path.dirname(__file__)
    config_path = os.path.normpath(os.path.join(src_dir, "../alpha/config"))

    handler = logging.StreamHandler()
    fmt = "%(asctime)s %(levelname)-1.1s %(name)s:%(funcName)s:%(lineno)s | %(message)s"
    formatter = logging.Formatter(fmt=fmt)
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)

    return cfg4py.init(config_path, False)


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]
        return port


async def is_local_omega_alive(port: int = 3181):
    try:
        url = f"http://localhost:{port}/sys/version"
        async with aiohttp.ClientSession() as client:
            async with client.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
        return True
    except Exception as e:
        return False


async def start_omega(timeout=60):
    port = find_free_port()

    cfg.omega.urls.quotes_server = f"http://localhost:{port}"
    account = os.environ["JQ_ACCOUNT"]
    password = os.environ["JQ_PASSWORD"]

    # hack: by default postgres is disabled, but we need it enabled for ut
    cfg_ = json.dumps({"postgres": {"dsn": cfg.postgres.dsn, "enabled": "true"}})

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "omega.app",
            "start",
            "--impl=jqadaptor",
            f"--cfg={cfg_}",
            f"--account={account}",
            f"--password={password}",
            f"--port={port}",
        ],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for i in range(timeout, 0, -1):
        await asyncio.sleep(1)
        if process.poll() is not None:
            # already exit
            out, err = process.communicate()
            logger.warning(
                "subprocess exited, %s: %s", process.pid, out.decode("utf-8")
            )
            raise subprocess.SubprocessError(err.decode("utf-8"))
        if await is_local_omega_alive(port):
            logger.info("omega server is listen on %s", cfg.omega.urls.quotes_server)
            return process

    raise subprocess.SubprocessError("Omega server malfunction.")


def _read_file(filename):
    from os.path import dirname, join

    df = pd.read_csv(
        join(dirname(__file__), filename),
        index_col=0,
        parse_dates=True,
        infer_datetime_format=True,
    )

    code = ".".join(filename.split(".")[:2])
    sec = Security(code)
    sec.load_bars_from_dataframe(df)


sh_index = _read_file("000001.XSHG.1d.csv")
"""DataFrame of sh index from 2012 to 2020"""

# async def main():
#     init_test_env()
#     await omicron.init()
#     sh_index = _read_file("000001.XSHG.1d.csv")


# if __name__ == '__main__':
#     asyncio.run(main())
