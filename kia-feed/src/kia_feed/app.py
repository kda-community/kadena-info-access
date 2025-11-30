import asyncio
import aiohttp
from collections import namedtuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pypact.chainweb import Chainweb
from pypact.signers import KdaSigner
from pypact.pact_rest_api import SignerCabability
from easydict import EasyDict
import yaml
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s:  %(message)s', level=logging.INFO)

DataElement = namedtuple("DataElement", "value timestamp")

global_data = {}
main_condition = asyncio.Condition()

CMC_SYMBOLS = ("KDA", "ETH", "BTC")
QUANTIZER = Decimal("0.000001")

def per_usd(x): return "{}/USD".format(x)

def compute_change(x,y): return 1000.0 if y == 0 else abs(x - y)/y

def pact_do_decimal(x):
    return Decimal(x["decimal"]) if isinstance(x, dict) else Decimal(x)

def pact_to_date(x): return datetime.fromisoformat(x["time"]) if "time" in x else datetime.fromisoformat(x["timep"])

def date_to_pact(x): return {"time":x.strftime("%Y-%m-%dT%H:%M:%SZ")}
def dec_to_pact(x): return {"decimal":str(x)}

def pact_to_element(x): return DataElement( pact_do_decimal(x["value"]), pact_to_date(x["timestamp"]))

CMC_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"

BLOCKNATIVE_URL = "https://api.blocknative.com/gasprices/blockprices"
GAS_CAP = SignerCabability("coin.GAS")

# Some global variable to make things easier
CONFIG = None
GAS_SIGNER = None
REPORT_SIGNER = None

class ChainwebNode(Chainweb):
    NAME = "Kadena Mainnet"
    MINIMUM_GAS_PRICE = 1e-8

    def __init__(self):
        super().__init__(CONFIG.common.pact_api)

def module(): return CONFIG.common.ns + ".kia-oracle"


def load_config():
    global CONFIG
    logging.info("Loading config")
    with open("config.yaml", "r") as fd:
        CONFIG = EasyDict(yaml.safe_load(fd))


def load_signers():
    global GAS_SIGNER
    global REPORT_SIGNER
    logging.info("Importing keys")
    GAS_SIGNER = KdaSigner.from_file(CONFIG.common.gas_key)
    REPORT_SIGNER = KdaSigner.from_file(CONFIG.common.reporter_key)
    logging.info("Gas signer ({}) = {}".format(CONFIG.common.sender, GAS_SIGNER.pubKey))
    logging.info("Report signer = {}".format(REPORT_SIGNER.pubKey))


async def ethprice_loop():
    global_data["EthGas"] = None
    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("Retrieving Eth gas price")
            try:
                async with session.get(BLOCKNATIVE_URL) as resp:
                    data = await resp.json()
                    async with main_condition:
                        gasPrice = Decimal(data["blockPrices"][0]["estimatedPrices"][2]["maxFeePerGas"]).quantize(QUANTIZER)
                        logging.info("Eth Gas Price = {}".format(gasPrice))
                        global_data["EthGas"] = DataElement(gasPrice, datetime.now(timezone.utc))
                        main_condition.notify_all()
            except Exception as ex:
                logging.warning("Error when trying to retrieve Eth Gas Price")
                logging.warning(ex)
            finally:
                await asyncio.sleep(280.0)


async def cmc_loop():
    headers = { "X-CMC_PRO_API_KEY": CONFIG.common.cmc_api_key, "Accept": "application/json"}
    params = {"symbol": ",".join(CMC_SYMBOLS)}

    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("Retrieving data from CoinMarketCap")
            async with session.get(CMC_URL, headers=headers, params=params) as resp:
                data = await resp.json()
                async with main_condition:
                    for symbol in CMC_SYMBOLS:
                        price = Decimal(data["data"][symbol][0]["quote"]["USD"]["price"]).quantize(QUANTIZER)
                        logging.info("{} = {}".format(symbol, price))
                        global_data[per_usd(symbol)] = DataElement(price, datetime.now(timezone.utc))
                    main_condition.notify_all()

            await asyncio.sleep(300.0)


async def chain_loop(chain):
    config = CONFIG.chains[str(chain.chain_id)]
    symbols = list(config.keys())
    current_data = {}

    # Wait for init of CoinMarket Cap
    async with main_condition:
        await main_condition.wait_for(lambda : len(global_data) >= 4)

    logging.info("Starting chain {} task".format(chain.chain_id))

    for symbol in symbols:
        result = await chain.local_result( '({}.get-value "{}")'.format(module(), symbol))
        current_data[symbol] = pact_to_element(result)
    logging.info("Chain {} Current data loaded".format(chain.chain_id))

    def age(symbol):
        return global_data[symbol].timestamp - current_data[symbol].timestamp

    def value_change(symbol):
        return compute_change(global_data[symbol].value, current_data[symbol].value)

    def too_old(symbol): return age(symbol) >= timedelta(seconds=config[symbol].max_delay) if global_data[symbol] else False
    def change_exceeded(symbol): return value_change(symbol) > config[symbol].max_delta if global_data[symbol] else False

    while True:

        trx_symbols = []
        trx_values = []
        trx_timestamps = []

        async with main_condition:
            await main_condition.wait_for(lambda :  any(map(too_old, symbols)) or any(map(change_exceeded, symbols)))
            logging.info("Chain {} requires an update".format(chain.chain_id))


            for symbol in symbols:
                if too_old(symbol) or change_exceeded(symbol):
                    trx_symbols.append(symbol)
                    trx_values.append(dec_to_pact(global_data[symbol].value))
                    trx_timestamps.append(date_to_pact(global_data[symbol].timestamp))
            logging.info("Chain {} Updating symbols :{}".format(chain.chain_id, " | ".join(trx_symbols)))

        cmd = chain.create_command("({}.set-multiple-values (read-msg 'k)(read-msg 'ts)(read-msg 'v))".format(module()), sender=CONFIG.common.sender, gasLimit=800)
        cmd.payload.data = {"k":trx_symbols, "ts":trx_timestamps, "v":trx_values}
        cmd.add_signer(GAS_SIGNER, GAS_CAP)
        cmd.add_signer(REPORT_SIGNER, SignerCabability("{}.REPORT".format(module())))

        await chain.send(cmd)
        logging.info("Chain {} Sent update Hash:{}".format(chain.chain_id, cmd.hash))

        async with asyncio.timeout(240.0):
            result = await chain.poll_until(cmd.hash)
            if not result[cmd.hash].successful:
                logging.info("Chain {} Trasnaction failure".format(chain.chain_id))
                await asyncio.sleep(600.0)
                continue

            logging.info("Chain {} Success".format(chain.chain_id))
            for symbol in trx_symbols:
                current_data[symbol] = global_data[symbol]

async def _main():
    asyncio.create_task(cmc_loop())
    asyncio.create_task(ethprice_loop())
    async with ChainwebNode() as cw:
        for c in map(int, CONFIG.chains):
            asyncio.create_task(chain_loop(cw.chains[c]))

        while True:
            await asyncio.sleep(1000.0)

def main():
    load_config()
    load_signers()
    asyncio.run(_main())



if __name__ == "__main__":
    main()
