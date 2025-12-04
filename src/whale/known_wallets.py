"""
Gheezy Crypto - База известных кошельков

Адреса крупных бирж, известных китов и функции определения владельца кошелька.
Работает для Ethereum, BSC и Bitcoin.
"""

from typing import Optional


# Известные адреса Ethereum
ETHEREUM_EXCHANGES: dict[str, str] = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance Cold Wallet",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1": "Binance Hot Wallet",
    # Coinbase
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase",
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511": "Coinbase",
    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x53d284357ec70ce289d6d64134dfac8e511c8a3d": "Kraken",
    "0x89e51fa8ca5d66cd220baed62ed01e8951aa7c40": "Kraken",
    # OKX (OKEx)
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX",
    "0xa7efae728d2936e78bda97dc267687568dd593f3": "OKX",
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128": "OKX",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": "Bybit",
    # KuCoin
    "0x2b5634c42055806a59e9107ed44d43c426e58258": "KuCoin",
    "0x689c56aef474df92d44a1b70850f808488f9769c": "KuCoin",
    # Huobi
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "Huobi",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": "Huobi",
    "0xfdb16996831753d5331ff813c29a93c76834a0ad": "Huobi",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Gemini",
    # Bitfinex
    "0x742d35cc6634c0532925a3b844bc454e4438f44e": "Bitfinex",
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Bitfinex",
}

# Известные адреса BSC (Binance Smart Chain)
BSC_EXCHANGES: dict[str, str] = {
    # Binance
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1": "Binance",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance Cold",
    # PancakeSwap
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": "PancakeSwap Router",
    "0x13f4ea83d0bd40e75c8222255bc855a974568dd4": "PancakeSwap",
    # Trust Wallet
    "0x55d398326f99059ff775485246999027b3197955": "USDT BSC",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    # KuCoin
    "0x2b5634c42055806a59e9107ed44d43c426e58258": "KuCoin",
    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
}

# Известные Bitcoin адреса
BITCOIN_EXCHANGES: dict[str, str] = {
    # Binance
    "34xp4vrocgjym3xr7ycvpfhocnxv4twseo": "Binance",
    "3m219krhrjfrkuwc2prkdvyd93yfpj2mwam": "Binance",
    "1ndc6nnfmcq5s3s8fk5dcjncrrqbqf6bkt": "Binance",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Binance Cold",
    # Coinbase
    "3kf9nxowq4assgtsgvam8pcwzggyqwl87": "Coinbase",
    "39wfudwsyyvlszmvecijrx3q3nlljgn": "Coinbase",
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": "Coinbase",
    # Kraken
    "3afybath9e3giuvhx9wlncvwm8uvv1xv8h": "Kraken",
    "bc1qf4s7xqq7kqxwqnj9pmqjnzexl5qzk6e4l5duzq": "Kraken",
    # Bitfinex
    "3d2oetdnuztajvv7ghbggmzffqaui3p9ae": "Bitfinex",
    "bc1qgxj97nskn8hc5apqvdl4h2lx7qxszd6v0xlrm4": "Bitfinex",
    # OKX
    "bc1qa5wkgaew2dkv56kfc6zpe4zwk6n57afst7n9fj": "OKX",
    # Bybit
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Bybit",
}

# Известные киты (whale wallets)
KNOWN_WHALES: dict[str, str] = {
    # Ethereum whales
    "0x73bceb1cd57c711feac4224d062b0f6ff338501e": "Ethereum Foundation",
    "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae": "Ethereum Foundation",
    "0x220866b1a2219f40e72f5c628b65d54268ca3a9d": "Genesis Whale",
    "0x7be8076f4ea4a4ad08075c2508e481d6c946d12b": "OpenSea",
    "0x00000000219ab540356cbb839cbe05303d7705fa": "ETH2 Deposit Contract",
}


def get_ethereum_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Ethereum адреса.

    Args:
        address: Адрес кошелька Ethereum

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    address_lower = address.lower()
    if address_lower in ETHEREUM_EXCHANGES:
        return ETHEREUM_EXCHANGES[address_lower]
    if address_lower in KNOWN_WHALES:
        return KNOWN_WHALES[address_lower]
    return None


def get_bsc_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для BSC адреса.

    Args:
        address: Адрес кошелька BSC

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    address_lower = address.lower()
    if address_lower in BSC_EXCHANGES:
        return BSC_EXCHANGES[address_lower]
    # BSC использует тот же формат адресов что и Ethereum
    if address_lower in ETHEREUM_EXCHANGES:
        return ETHEREUM_EXCHANGES[address_lower]
    return None


def get_bitcoin_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Bitcoin адреса.

    Args:
        address: Адрес кошелька Bitcoin

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    address_lower = address.lower()
    if address_lower in BITCOIN_EXCHANGES:
        return BITCOIN_EXCHANGES[address_lower]
    return None


def get_wallet_label(address: str, blockchain: str) -> Optional[str]:
    """
    Получить метку для адреса на указанном блокчейне.

    Args:
        address: Адрес кошелька
        blockchain: Название блокчейна (ethereum, bsc, bitcoin)

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    blockchain_lower = blockchain.lower()
    if blockchain_lower in ("ethereum", "eth"):
        return get_ethereum_wallet_label(address)
    elif blockchain_lower in ("bsc", "bnb", "binance"):
        return get_bsc_wallet_label(address)
    elif blockchain_lower in ("bitcoin", "btc"):
        return get_bitcoin_wallet_label(address)
    return None


def is_exchange_address(address: str, blockchain: str) -> bool:
    """
    Проверить, является ли адрес адресом биржи.

    Args:
        address: Адрес кошелька
        blockchain: Название блокчейна

    Returns:
        bool: True если адрес принадлежит бирже
    """
    label = get_wallet_label(address, blockchain)
    if label is None:
        return False
    # Проверяем, содержит ли метка название известной биржи
    exchange_keywords = [
        "binance", "coinbase", "kraken", "okx", "bybit",
        "kucoin", "huobi", "gemini", "bitfinex", "gate"
    ]
    label_lower = label.lower()
    return any(keyword in label_lower for keyword in exchange_keywords)


def get_short_address(address: str) -> str:
    """
    Получить сокращённый адрес.

    Args:
        address: Полный адрес кошелька

    Returns:
        str: Сокращённый адрес (первые 8 и последние 6 символов)
    """
    if len(address) <= 14:
        return address
    return f"{address[:8]}...{address[-6:]}"
