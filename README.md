# KIA : Kadena Info Access

Since DIA Oracle stopped to broadcast price on the blockchain.
This was unfortunatelly required by some Dapps and Wallets to show accurate information to users.

The new service called KIA (not DIA), will be used to publish some freely usable data.
Do not use this as an absolute Oracle for DeFi. Only for infirmation purpose.

## Smart contract and API

Deployed on Mainnet xxxxxx.kia-oracle

### Object value-schema
```pact
(defschema value-schema
    timestamp:time
    value:decimal)
```

### Function get-value
**key** *string* -> *object{value-schema}*

Return a value stored in the Oracle.

## Provided Data

Some informations may eb added in the future.

#### Chains 0 / 1
**KDA/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.

**BTC/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.

**ETH/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.


#### Chains 2
**KDA/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.

**BTC/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.

**ETH/USD**: Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 1% change.

**EthGas**: (ETH average Gas price in Gwei/Gas): Refreshed frequency: no less than 1 / hour. Forced refresh in case of more than 10% change.


#### Chains 3/19
**KDA/USD**: Refreshed frequency: no less than 1 / day. Forced refresh in case of more than 5% change.

**BTC/USD**: Refreshed frequency: no less than 1 / day. Forced refresh in case of more than 5% change.

**ETH/USD**: Refreshed frequency: no less than 1 / day. Forced refresh in case of more than 5% change.
