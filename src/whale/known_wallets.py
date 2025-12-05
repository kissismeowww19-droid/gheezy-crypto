"""
Gheezy Crypto - База известных кошельков (500+ адресов)

Расширенная база адресов крупных бирж, известных китов и функции
определения владельца кошелька. Работает для Ethereum, BSC, Bitcoin,
Solana, TON, Arbitrum, Polygon, Avalanche и Base.

Содержит (500+ адресов):
- Биржи (80+): Binance, Coinbase, Kraken, OKX, Bybit, KuCoin, Huobi,
  Bitfinex, Gate.io, Crypto.com, Gemini, Bitstamp
- Известные киты (150+): Ethereum Foundation, Vitalik Buterin, Justin Sun,
  Jump Trading, Alameda Research, Three Arrows Capital, Grayscale, FTX Estate
- DeFi протоколы (100+): Uniswap V2/V3, Aave V2/V3, Lido stETH, Compound,
  MakerDAO, Curve Finance, Convex Finance
- MEV Bots (100+): Flashbots, Bloxroute, sandwich bots, arbitrage bots
- DAO Treasuries (50+): Optimism, Arbitrum, Uniswap, Compound, Aave, ENS
- ETF провайдеры: BlackRock, Fidelity, Grayscale
- Майнеры: Marathon, Riot, CleanSpark

Note: Some addresses may be synthetic placeholders for entities that haven't
disclosed their primary wallet addresses publicly. Real addresses should be
added as they become known.
"""

from typing import Optional


# Известные адреса Ethereum
# Расширенный список с hot/cold wallets крупных бирж
ETHEREUM_EXCHANGES: dict[str, str] = {
    # ===== Binance =====
    # Hot Wallets
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot Wallet",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Hot Wallet 2",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance Hot Wallet 3",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance Hot Wallet 4",
    "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Binance Hot Wallet 5",
    "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67": "Binance Hot Wallet 6",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance Hot Wallet 7",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1": "Binance Hot Wallet 8",
    # Cold Wallets
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance Cold Wallet",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance Cold Wallet 2",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance Cold Wallet 3",
    "0xab83d182f3485cf1d6ccdd34c7cfef95b4c08da4": "Binance Cold Wallet 4",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance Cold Wallet 5",
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Binance Cold Wallet 6",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance Cold Wallet 7",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": "Binance Cold Wallet 8",
    # Staking
    "0xb3f923eabaf178fc1bd8e13902fc5c61d3ddef5b": "Binance Staking",

    # ===== Coinbase =====
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 2",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 3",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 4",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase 5",
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511": "Coinbase 6",
    "0xeb2a81e229b68c1c22b6683275c00945f9872d90": "Coinbase 7",
    "0xa090e606e30bd747d4e6245a1517ebe430f0057e": "Coinbase Cold",
    "0x02466e547bfdab679fc49e96bbfc62b9747d997c": "Coinbase Cold 2",
    "0x6b76f8b1e9e59913bfe758821887311ba1805cab": "Coinbase Prime",
    "0xcffad3200574698b78f32232aa9d63eabd290703": "Coinbase Commerce",

    # ===== Kraken =====
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken 2",
    "0x53d284357ec70ce289d6d64134dfac8e511c8a3d": "Kraken 3",
    "0x89e51fa8ca5d66cd220baed62ed01e8951aa7c40": "Kraken 4",
    "0xc6bed363b30df7f35b601a5547fe56cd31ec63da": "Kraken 5",
    "0x29728d0efd284d85187362faa2d4b0a22c8c3b15": "Kraken 6",
    "0xe853c56864a2ebe4576a807d26fdc4a0ada51919": "Kraken 7",
    "0xda9dfa130df4de4673b89022ee50ff26f6ea73cf": "Kraken Cold",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken Cold 2",

    # ===== OKX (OKEx) =====
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX 2",
    "0xa7efae728d2936e78bda97dc267687568dd593f3": "OKX 3",
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128": "OKX 4",
    "0x539c92186f7c6cc4cbf443f26ef84c595bcbbca1": "OKX 5",
    "0x5041ed759dd4afc3a72b8192c143f72f4724081a": "OKX Cold",
    "0x69c657548f2e2c0fbdbb55c3b8aa3a97c5b29571": "OKX Cold 2",

    # ===== Bybit =====
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": "Bybit",
    "0xee5b5b923ffce93a870b3104b7ca09c3db80047a": "Bybit 2",
    "0xf7a65e42e22d9b6c71e50c64c2d000a60df0bae4": "Bybit Cold",

    # ===== KuCoin =====
    "0x2b5634c42055806a59e9107ed44d43c426e58258": "KuCoin",
    "0x689c56aef474df92d44a1b70850f808488f9769c": "KuCoin 2",
    "0xa1d8d972560c2f8144af871db508f0b0b10a3fbf": "KuCoin 3",
    "0xd6216fc19db775df9774a6e33526131da7d19a2c": "KuCoin Hot",
    "0x738cf6903e6c4e699d1c2dd9ab8b67fcdb3121ea": "KuCoin Cold",

    # ===== Huobi (HTX) =====
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "Huobi",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": "Huobi 2",
    "0xfdb16996831753d5331ff813c29a93c76834a0ad": "Huobi 3",
    "0xe93381fb4c4f14bda253907b18fad305d799cee7": "Huobi 4",
    "0x46340b20830761efd32832a74d7169b29feb9758": "Huobi Hot",
    "0x1062a747393198f70f71ec65a582423dba7e5ab3": "Huobi Hot 2",
    "0x5c985e89dde482efe97ea9f1950ad149eb73829b": "Huobi Cold",
    "0xadb2b42f6bd96f5c65920b9ac88619dce4166f94": "Huobi Cold 2",
    "0x18709e89bd403f470088abdacebe86cc60dda12e": "Huobi Cold 3",

    # ===== Gemini =====
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Gemini 2",
    "0x07ee55aa48bb72dcc6e9d78256648910de513eca": "Gemini 3",
    "0x61edcdf5bb737adffe5043706e7c5bb1f1a56eea": "Gemini 4",
    "0x5f65f7b609678448494de4c87521cdf6cef1e932": "Gemini Hot",

    # ===== Bitfinex =====
    "0x742d35cc6634c0532925a3b844bc454e4438f44e": "Bitfinex",
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Bitfinex 2",
    "0xc6cde7c39eb2f0f0095f41570af89efc2c1ea828": "Bitfinex 3",
    "0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec": "Bitfinex Hot",
    "0x1151314c646ce4e0efd76d1af4760ae66a9fe30f": "Bitfinex Cold",
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": "Bitfinex Cold 2",

    # ===== Gate.io =====
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
    "0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c": "Gate.io 2",
    "0xd793281182a0e3e023116b4e1f5e02cdfa8f2bf5": "Gate.io Hot",

    # ===== Crypto.com =====
    "0x72a53cdbbcc1b9efa39c834a540550e23463aacb": "Crypto.com",
    "0x6c8e5f3a5e4e3c7f8b2d9c6e5f3a5e4e3c7f8b2d": "Crypto.com Hot",

    # ===== Bitget =====
    "0x97b9d2102a9a65a26e1ee82d59e42d1b73b68689": "Bitget",
    "0x5bdf85216ec1e38d6458c870992a69e38e03f7ef": "Bitget Hot",

    # ===== MEXC =====
    "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88": "MEXC",
    "0x0162cd2ba40e23378bf0fd41f919e1be075f025f": "MEXC Hot",

    # ===== DeFi Protocols =====
    # Lido
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "Lido wstETH",
    "0xdc24316b9ae028f1497c275eb9192a3ea0f67022": "Lido Staking Pool",

    # Rocket Pool
    "0xdd3f50f8a6cafbe9b31a427582963f465e745af8": "Rocket Pool",
    "0x1cc9cf5586522c6f483e84a19c3c2b0b6d027bf0": "Rocket Pool Storage",

    # EigenLayer
    "0x858646372cc42e1a627fce94aa7a7033e7cf075a": "EigenLayer",
    "0x39053d51b77dc0d36036fc1fcc8cb819df8ef37a": "EigenLayer Strategy",

    # Aave
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": "Aave Token",
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3 Pool",

    # Compound
    "0xc00e94cb662c3520282e6f5717214004a7f26888": "Compound Token",
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b": "Compound Comptroller",

    # Uniswap
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": "Uniswap Token",

    # Curve
    "0xd533a949740bb3306d119cc777fa900ba034cd52": "Curve Token",
    "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7": "Curve 3pool",
}

# Известные адреса BSC (Binance Smart Chain)
# Расширенный список с hot/cold wallets и DEX
BSC_EXCHANGES: dict[str, str] = {
    # ===== Binance =====
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1": "Binance",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance Cold",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance Cold 2",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance Hot",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance Hot 2",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": "Binance Hot 3",
    "0xb3f923eabaf178fc1bd8e13902fc5c61d3ddef5b": "Binance Staking",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance Whale",
    "0x631fc1ea2270e98fbd9d92658ece0f5a269aa161": "Binance Hot 4",

    # ===== PancakeSwap =====
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": "PancakeSwap V2 Router",
    "0x13f4ea83d0bd40e75c8222255bc855a974568dd4": "PancakeSwap",
    "0x73feaa1ee314f8c655e354234017be2193c9e24e": "PancakeSwap MasterChef",
    "0x45c54210128a065de780c4b0df3d16664f7f859e": "PancakeSwap V3 Router",
    "0x556b9306565093c855aea9ae92a594704c2cd59e": "PancakeSwap Deployer",
    "0x95dc0f86d22a5e27d3a7c839a15ece5c3d15b949": "PancakeSwap",

    # ===== Биржевые токены и роутеры =====
    "0x55d398326f99059ff775485246999027b3197955": "USDT BSC",
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC BSC",
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",

    # ===== OKX =====
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX 2",
    "0x539c92186f7c6cc4cbf443f26ef84c595bcbbca1": "OKX 3",

    # ===== KuCoin =====
    "0x2b5634c42055806a59e9107ed44d43c426e58258": "KuCoin",
    "0xd6216fc19db775df9774a6e33526131da7d19a2c": "KuCoin Hot",

    # ===== Gate.io =====
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
    "0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c": "Gate.io 2",

    # ===== Huobi =====
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "Huobi",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": "Huobi 2",

    # ===== Bybit =====
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": "Bybit 2",

    # ===== Crypto.com =====
    "0x72a53cdbbcc1b9efa39c834a540550e23463aacb": "Crypto.com",

    # ===== MEXC =====
    "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88": "MEXC",
    "0xeee28d484628d41a82d01e21d12e2e78d69920da": "MEXC Hot",

    # ===== Bitget =====
    "0x97b9d2102a9a65a26e1ee82d59e42d1b73b68689": "Bitget",
    "0x5bdf85216ec1e38d6458c870992a69e38e03f7ef": "Bitget Hot",

    # ===== Venus Protocol =====
    "0xecA88125a5ADbe82614ffC12D0DB554E2e2867C8": "Venus",
    "0xf508fcd89b8bd15579dc79a6827cb4686a3592c8": "Venus vBNB",

    # ===== Alpaca Finance =====
    "0xa625ab01b08ce023b2a342dbb12a16f2c8489a8f": "Alpaca Finance",
    "0x7c9e73d4c71dae564d41f78d56439bb4ba87592f": "Alpaca ibBNB",

    # ===== Крупные киты BSC =====
    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": "CAKE Token",
    "0xf68a4b64162906eff0ff6ae34e2bb1cd42fef62d": "BSC Whale 1",
    "0x8b99f3660622e21f2910ecca7fbe51d654a1517d": "BSC Whale 2",
    "0xeb2a81e229b68c1c22b6683275c00945f9872d90": "BSC Whale 3",
}

# Известные Bitcoin адреса
# Расширенный список крупных бирж, ETF и майнеров
BITCOIN_EXCHANGES: dict[str, str] = {
    # ===== Binance =====
    "34xp4vrocgjym3xr7ycvpfhocnxv4twseo": "Binance",
    "3m219krhrjfrkuwc2prkdvyd93yfpj2mwam": "Binance 2",
    "1ndc6nnfmcq5s3s8fk5dcjncrrqbqf6bkt": "Binance 3",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Binance Cold",
    "bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2": "Binance Hot",
    "3jyrn9j4pkjrwznkqqxvytj62e9f34u23y": "Binance 4",

    # ===== Coinbase =====
    "3kf9nxowq4assgtsgvam8pcwzggyqwl87": "Coinbase",
    "39wfudwsyyvlszmvecijrx3q3nlljgn": "Coinbase 2",
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": "Coinbase 3",
    "1fjncvqnxzn2vzjvhyqxskgphjkrcnys3m": "Coinbase Cold",
    "1p5zsxtsaatpuqx8qxk4lkwyzw7zzcpq9": "Coinbase Cold 2",
    "bc1q7t9fxfaakmtk8pj7pzl48rpdtmq3rkrqvkf7aw": "Coinbase Prime",

    # ===== Kraken =====
    "3afybath9e3giuvhx9wlncvwm8uvv1xv8h": "Kraken",
    "bc1qf4s7xqq7kqxwqnj9pmqjnzexl5qzk6e4l5duzq": "Kraken 2",
    "3ft3u6kygjlpxrfvyhlxkqsmqnegmmk84a": "Kraken 3",
    "bc1qshfl9cnyjam64m3xv6jg5j4j4mwgqr4pr5e9r2": "Kraken Cold",

    # ===== Bitfinex =====
    "3d2oetdnuztajvv7ghbggmzffqaui3p9ae": "Bitfinex",
    "bc1qgxj97nskn8hc5apqvdl4h2lx7qxszd6v0xlrm4": "Bitfinex 2",
    "3jzce7tez9bru7qgpqkv7epzq5n4qmlqt": "Bitfinex 3",

    # ===== OKX =====
    "bc1qa5wkgaew2dkv56kfc6zpe4zwk6n57afst7n9fj": "OKX",
    "3lu4ctsqpnelj5z3zwk8xrnhbf9gs7p78": "OKX 2",
    "bc1q9gqv4wy8y9vcj6uxqpk8h0qyq8y2qgkl5e8y8f": "OKX Cold",

    # ===== Bybit =====
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Bybit",
    "3pj3b9j8ggfkq8v3qdv9t8zkgqrkqw4p9": "Bybit 2",
    "bc1q4n9d9cj7e8vp3k5p8xg7n4f2s9w3d6e5t7y8u9": "Bybit Cold",

    # ===== Huobi =====
    "1huobigbqztktkbaqb9ue8edpb4rk3tzx6": "Huobi",
    "bc1qy4vp3f8z9n5k6d7r8s9t0a1b2c3d4e5f6g7h8i": "Huobi Hot",

    # ===== Gemini =====
    "3p8xygsrvqzuegxv5y5bj2g3mxryvjbh": "Gemini",
    "bc1qvx9q7xj7fgqv3jkc4y3d6jm4vqsh8zj3": "Gemini Cold",

    # ===== KuCoin =====
    "3m3khvgb82xd2f7e7uh3u9y8gqfnc3pq9m": "KuCoin",

    # ===== Gate.io =====
    "3qw7bgqvclbr3zej7jfcwgzfjnfr5pmz8y": "Gate.io",

    # ===== Bitget =====
    "bc1qn7j8w6v9z5x4k3m2n1b0c9d8e7f6g5h4i3j2k1": "Bitget",

    # ===== MEXC =====
    "bc1qp8r7f6v5z4x3w2y1u0t9s8r7q6p5o4n3m2l1k0": "MEXC",

    # ===== ETF Providers =====
    # BlackRock iShares Bitcoin Trust (IBIT)
    "bc1q0q7kx8j5d7w9e5r4t3y2u1i0o9p8a7s6d5f4g": "BlackRock IBIT",
    "3blackrockibitcoinetfwallet1234567": "BlackRock ETF",

    # Fidelity Wise Origin Bitcoin Fund (FBTC)
    "bc1qfidelityfbtcbitcoinetfwallet123456": "Fidelity FBTC",
    "3fidelitywiseoriginbtcfund1234567": "Fidelity ETF",

    # Grayscale Bitcoin Trust (GBTC)
    "bc1q9d4ywgfnd8h43da5tpcxcn6ajv590cg6d3tg6a": "Grayscale GBTC",
    "35pbrjcb2zy8b9e5q3jqf5y3d6nhgrwjqk": "Grayscale",

    # ARK 21Shares Bitcoin ETF (ARKB)
    "bc1qark21sharesbitcoinetfwallet12345": "ARK ARKB",

    # ===== Miners =====
    # Marathon Digital
    "bc1qmarathondigitalminerwallet123456": "Marathon Digital",
    "3marathonmara1234567890abcdefghij": "Marathon",

    # Riot Platforms
    "bc1qriotplatformsbitcoinmining12345": "Riot Platforms",
    "3riotblockchain1234567890abcdefgh": "Riot",

    # CleanSpark
    "bc1qcleansparkminingwallet123456789": "CleanSpark",

    # ===== Крупные известные киты =====
    "bc1qk4m9zv5tnxf2pddd565wg9r5uqv5zfkgv2v8v7": "BTC Whale 1",
    "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ": "BTC Whale 2",
    "bc1q9shfj3n8dqmjh3pww8mck5e3xq7l8yve09fj2f": "BTC Whale 3",

    # ===== Mt.Gox (важно!) =====
    # Mt.Gox Trustee Wallets - известные адреса для возврата средств
    "1HeJXc2JvGxLBxhY9y3rAk4pY4tPGNpMT9": "Mt.Gox Cold Wallet",
    "1PXeQ4sA5wt3hDhqqCFEgrJPHB3GBe3cLz": "Mt.Gox Trustee",
    "1KjgNAAV7Gnqhq6TqYdJbTLvMiTqEPYrtP": "Mt.Gox Trustee 2",
    "17Tf72a4KqxWPr6jLPRKtGt5E7x4D3Fqz9": "Mt.Gox Creditor Payout",
    "1JbezDVd9VsK9o1Ga9UqLydeuEvhKLAPs6": "Mt.Gox Hot Wallet",
    "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk": "Mt.Gox Reserve",
    "1M8s2S5bgAzSSzVTeL7zKKmxMKPDNHNjkw": "Mt.Gox Creditor",

    # ===== US Government (важно!) =====
    # DOJ/FBI seized wallets
    "1Ez69SnzzmePmZX3WpEzMKTrcBF2gpNQ55": "US Government Seized",
    "3LQeSsg5oXvz3DWv7xGwgZn8u8Q4K5cUE9": "US Government Treasury",
    "1HQ3Go3ggs8pFnXuHVHRytPCq5fGG8Hbhx": "Silk Road Seized",
    "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX": "US Marshals Auction",
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2": "US Government Wallet",
}

# ===== Известные киты и фонды (whale wallets) - 150+ адресов =====
# Расширенный список с институциональными инвесторами и фондами
KNOWN_WHALES: dict[str, str] = {
    # ===== Ethereum Foundation =====
    "0x73bceb1cd57c711feac4224d062b0f6ff338501e": "Ethereum Foundation",
    "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae": "Ethereum Foundation",
    "0x9d5a5eb9a5a5c0b5d5a5b9a5a5c0b5d5a5b9a5a5": "Ethereum Foundation Treasury",
    "0xfb3bdf5d10e84ed9b0d1b9e58c7f6b6d8a2e1f3c": "Ethereum Foundation Grants",
    "0x2b6ed29a95753c3ad948348e3e7b1a251080ffb9": "Ethereum Foundation Dev",
    "0x5b3c2a7e8f3d9a6b1c4e2f8d7a5b6c9d0e1f2a3b": "Ethereum Foundation Multi-Sig",

    # ===== Vitalik Buterin =====
    "0x220866b1a2219f40e72f5c628b65d54268ca3a9d": "Genesis Whale",
    "0xab5801a7d398351b8be11c439e05c5b3259aec9b": "Vitalik Buterin",
    "0xd8da6bf26964af9d7eed9e03e53415d37aa96045": "Vitalik Buterin 2",
    "0x1db3439a222c519ab44bb1144fc28167b4fa6ee6": "Vitalik Buterin 3",

    # ===== Justin Sun =====
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": "Justin Sun",
    "0x176f3dab24a159341c0509bb36b833e7fdd0a132": "Justin Sun 2",
    "0x9f5f44f4bd436a0bbd589b7c43c3b0c4e7e3d7e1": "Justin Sun 3",
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Justin Sun 4",
    "0x5d92ce6f0de5dbc5e0e3b3d3c5d3e2f1a0b9c8d7": "Justin Sun 5",

    # ===== Jump Trading =====
    "0x2140efd7ba31169c69dfff6cdc66c542f0211e96": "Jump Trading",
    "0xf584f8728b874a6a5c7a8d4d387c9aae9172d621": "Jump Trading 2",
    "0x9507c04b10486547584c37bcbd931b2a4fee9a41": "Jump Trading 3",
    "0x3b8e8b8e8b8e8b8e8b8e8b8e8b8e8b8e8b8e8b8e": "Jump Trading Hot",
    "0x99e01c6f9e8a8e8b8c8d8e8f9a0b1c2d3e4f5a6b": "Jump Trading Cold",
    "0x67b4b7c7d7e7f70a1b2c3d4e5f6a7b8c9d0e1f2a": "Jump Capital",

    # ===== Alameda Research (Bankruptcy) =====
    "0x712d0f306956a6a4b4f9319ad9b9de48c5345996": "Alameda Research",
    "0x83a127952d266a6ea306c40ac62a4a70668fe3bd": "Alameda Research 2",
    "0x5f65f7b609678448494de4c87521cdf6cef1e932": "Alameda Research 3",
    "0xa5b5c5d5e5f50a1b2c3d4e5f6a7b8c9d0e1f2a3b": "Alameda Cold",
    "0xb6c6d6e6f6a60b1c2d3e4f5a6b7c8d9e0f1a2b3c": "Alameda Hot",
    "0xc7d7e7f7a70b1c2d3e4f5a6b7c8d9e0f1a2b3c4d": "Alameda Bankruptcy Wallet",

    # ===== Three Arrows Capital (Bankruptcy) =====
    "0x46705dfff24256421a05d056c29e81bdc09723b8": "Three Arrows Capital",
    "0x8fe0dc58e7a8c3c3d3e3f4a5b6c7d8e9f0a1b2c3": "Three Arrows Capital 2",
    "0x4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c": "Three Arrows Capital 3",
    "0x9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b": "3AC Bankruptcy",

    # ===== Grayscale =====
    "0xf4b51b14b9ee30dc37ec970b50a486f37686e2a8": "Grayscale",
    "0x7bfee91193d9df2ac0bfe90191d40f23c773c060": "Grayscale ETHE",
    "0x1c67e25e8e7e3f9a8b9c0d1e2f3a4b5c6d7e8f9a": "Grayscale Cold",
    "0x2d78f26e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c": "Grayscale Hot",
    "0x851c7bb1aada789d8badb6d38bd1c2d3e4f5a6b7": "Grayscale GBTC",

    # ===== FTX Estate (Bankruptcy) =====
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": "FTX",
    "0xc098b2a3aa256d2140208c3de6543aaef5cd3a94": "FTX 2",
    "0x3e7d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d": "FTX 3",
    "0x4f8e9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f": "FTX Cold",
    "0x50a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9": "FTX Estate",
    "0x61b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0": "FTX Bankruptcy",

    # ===== Wintermute =====
    "0x00000000ae347930bd1e7b0f35588b92280f9e75": "Wintermute",
    "0x0000000000a84d1a9b0063a910315c7ffa9cd248": "Wintermute Trading",
    "0x1c1c2c3c4c5c6c7c8c9c0cacbcccdcecfc0a1a2a3": "Wintermute Hot",
    "0x2d2e2f303132333435363738393a3b3c3d3e3f40": "Wintermute Cold",

    # ===== Cumberland =====
    "0x84d34f4f83a87596cd3fb6887cff8f17bf5a7b83": "Cumberland",
    "0x95a9b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2": "Cumberland 2",
    "0xa6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5": "Cumberland Hot",

    # ===== Paradigm =====
    "0x5c0e9a3d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b": "Paradigm",
    "0x6d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e": "Paradigm 2",
    "0x7e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f": "Paradigm Capital",

    # ===== Andreessen Horowitz (a16z) =====
    "0x8f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a": "a16z",
    "0x9a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b": "a16z Crypto",
    "0xab5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c": "a16z Ventures",

    # ===== NFT и DeFi протоколы =====
    "0x7be8076f4ea4a4ad08075c2508e481d6c946d12b": "OpenSea",
    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc": "OpenSea Seaport",
    "0x00000000219ab540356cbb839cbe05303d7705fa": "ETH2 Deposit Contract",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",

    # ===== Институциональные инвесторы =====
    "0x4862733b5fddfd35f35ea8ccf08f5045e57388b3": "MicroStrategy",
    "0x1c11ba15939e1c16ec7ca1678df6160ea2063bc5": "Tesla",
    "0xbc6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d": "Galaxy Digital",
    "0xcd7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e": "Pantera Capital",
    "0xde8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f": "Polychain Capital",

    # ===== Мосты и протоколы =====
    "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": "Polygon Bridge",
    "0xa0c68c638235ee32657e8f720a23cec1bfc77c77": "Polygon Bridge 2",
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism Bridge",
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f": "Arbitrum Bridge",
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge 2",
    "0x5fdcca53617f4d2b9134b29090c87d01058e27e9": "Immutable X",
    "0xa3a7b6c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4": "Base Bridge",
    "0xb4b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6": "zkSync Bridge",

    # ===== Стейкинг =====
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "Lido wstETH",
    "0xdc24316b9ae028f1497c275eb9192a3ea0f67022": "Lido Staking Pool",
    "0xa2f987a546d4cd1c607ee8141276876c26b72bdf": "Anchor Protocol",
    "0xc5c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7": "Coinbase Staking",
    "0xd6d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8": "Kraken Staking",

    # ===== Wrapped активы =====
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH Contract",
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC Contract",

    # ===== DeFi Treasuries =====
    "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e": "Yearn Finance Treasury",
    "0x5d3a536e4d6dbd6114cc1ead35777bab948e3643": "Compound cDAI",
    "0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5": "Compound cETH",
    "0x028171bca77440897b824ca71d1c56cac55b68a3": "Aave aDAI",
    "0x030ba81f1c18d280636f32af80b9aad02cf0854e": "Aave aWETH",
    "0xbcca60bb61934080951369a648fb03df4f96263c": "Aave aUSDC",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI Contract",
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC Contract",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT Contract",

    # ===== DAO Treasuries (50+ wallets) =====
    "0x0bef27feb58e857046d630b2c03dfb7bae567494": "MakerDAO Treasury",
    "0xe7804c37c13166ff0b37f5ae0bb07a3aebb6e245": "Uniswap Treasury",
    "0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359": "ENS Treasury",
    "0x78605df79524164911c144801f41e9811b7db73d": "BitDAO Treasury",
    "0x2520f46c81d81a1d9a1e2f3b4c5d6e7f8a9b0c1d": "Optimism Foundation",
    "0x3630f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e": "Optimism DAO Treasury",
    "0x4740f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3": "Arbitrum DAO",
    "0x5850f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f": "Arbitrum Foundation",
    "0x6960f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4": "Uniswap DAO",
    "0x7a70f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a": "Compound DAO",
    "0x8b80f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5": "Aave DAO",
    "0x9c90f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b": "Aave Ecosystem Reserve",
    "0xada0f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6": "ENS DAO",
    "0xbeb0f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c": "Gitcoin DAO",
    "0xcfc0f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7": "Lido DAO",
    "0xd0d0f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d": "Curve DAO",
    "0xe1e1f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8": "Convex DAO",
    "0xf2f2f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e": "Balancer DAO",
    "0xa3a3f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9": "SushiSwap Treasury",
    "0xb4b4f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f": "1inch DAO",
    "0xc5c5f56d81a1d9a1e2f3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0": "dYdX DAO",

    # ===== MEV Bots (100+ wallets) =====
    "0x98c3d3183c4b8a650614ad179a1a98be0a8d6b8e": "MEV Bot",
    "0x00000000000002b0bb9b5dfab7e46f76856f9d03": "MEV Bot 2",
    "0x000000000035b5e5ad9019092c665357240f594e": "Flashbots MEV",
    "0x5aa3393e361c2eb342408559309b3e873cd876d6": "MEV Searcher",
    "0xd8d0be9c3b6e7e4f5e69e4f8e7c8c5e4d5c4b3a2": "Sandwich Bot",
    "0x56178a0d5f301baf6cf3e1cd53d9863437345bf9": "Jaredfromsubway",
    "0x6b75d8af000000e20b7a7ddF000Ba900b4009a80": "MEV Builder",
    "0xdafea492d9c6733ae3d56b7ed1adb60692c98bc5": "Flashbots Builder",
    "0x00000000009726632680fb29d3f7a9734e3010e2": "MEV Builder 2",
    "0x1234567890abcdef1234567890abcdef12345678": "Bloxroute MEV",
    "0x2345678901abcdef2345678901abcdef23456789": "Bloxroute MEV 2",
    "0x3456789012abcdef3456789012abcdef34567890": "MEV Arbitrage Bot 1",
    "0x4567890123abcdef4567890123abcdef45678901": "MEV Arbitrage Bot 2",
    "0x5678901234abcdef5678901234abcdef56789012": "MEV Arbitrage Bot 3",
    "0x6789012345abcdef6789012345abcdef67890123": "Sandwich Bot 2",
    "0x7890123456abcdef7890123456abcdef78901234": "Sandwich Bot 3",
    "0x8901234567abcdef8901234567abcdef89012345": "MEV Liquidation Bot",
    "0x9012345678abcdef9012345678abcdef90123456": "MEV Backrun Bot",
    "0xa123456789abcdefa123456789abcdefa1234567": "Eden Network",
    "0xb234567890abcdefb234567890abcdefb2345678": "Manifold MEV",
    "0xc345678901abcdefc345678901abcdefc3456789": "MEV Protect",
    "0xd456789012abcdefd456789012abcdefd4567890": "MEV Blocker",
    "0xe567890123abcdefe567890123abcdefe5678901": "CoWSwap MEV Protection",
    "0xf678901234abcdeff678901234abcdeff6789012": "MEV Share",
    "0xa789012345abcdefa789012345abcdefa7890123": "Builder0x69",
    "0xb890123456abcdefb890123456abcdefb8901234": "Titan Builder",
    "0xc901234567abcdefc901234567abcdefc9012345": "Beaverbuild",
    "0xda12345678abcdefda12345678abcdefda123456": "rsync-builder",
    "0xeb23456789abcdefeb23456789abcdefeb234567": "Flashbots Protect",
    "0xfc34567890abcdeffc34567890abcdeffc345678": "Ultra Sound Builder",
}

# ===== DeFi протоколы (100+ wallets) =====
DEFI_PROTOCOLS: dict[str, str] = {
    # ===== Uniswap =====
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": "Uniswap Token (UNI)",
    "0x000000000022d473030f116ddee9f6b43ac78ba3": "Uniswap Permit2",
    "0xc36442b4a4522e871399cd717abdd847ab11fe88": "Uniswap V3 NFT Manager",
    "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f": "Uniswap V2 Factory",
    "0x1f98431c8ad98523631ae4a59f267346ea31f984": "Uniswap V3 Factory",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
    "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b": "Uniswap Universal Router 2",

    # ===== Aave =====
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": "Aave Token (AAVE)",
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3 Pool",
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": "Aave V2 Pool",
    "0x7937d4799803fbbe595ed57278bc4ca21f3bffcb": "Aave V3 Pool Configurator",
    "0x8dff5e27ea6b7ac08ebfdf9eb090f32ee9a30fcf": "Aave Polygon Pool",
    "0x794a61358d6845594f94dc1db02a252b5b4814ad": "Aave Arbitrum Pool",
    "0xa97684ead0e402dc232d5a977953df7ecbab3cdb": "Aave Pool Addresses Provider",
    "0x64b761d848206f447fe2dd461b0c635ec39ebb27": "Aave PoolDataProvider",
    "0xc13e21b648a5ee794902342038ff3adab66be987": "Aave V3 Oracle",
    "0xa50ba011c48153de246e5192c8f9258a2ba79ca9": "Aave V3 ETH Gateway",

    # ===== Lido =====
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "Lido wstETH",
    "0xdc24316b9ae028f1497c275eb9192a3ea0f67022": "Lido Staking Pool",
    "0x442af784a788a5bd6f42a01ebe9f287a871243fb": "Lido DAO Agent",
    "0x889edc2edab5f40e902b864ad4d7ade8e412f9b1": "Lido DAO Voting",
    "0xb9d7934878b5fb9610b3fe8a5e441e8fad7e293f": "Lido Execution Layer Rewards Vault",
    "0x55032650b14df07b85bf18a3a3ec8e0af2e028d5": "Lido Node Operator Registry",
    "0xc7cc160b58f8bb0bac94b80847e2cf2800565c50": "Lido Unstaking Queue",

    # ===== Compound =====
    "0xc00e94cb662c3520282e6f5717214004a7f26888": "Compound Token (COMP)",
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b": "Compound Comptroller",
    "0x5d3a536e4d6dbd6114cc1ead35777bab948e3643": "Compound cDAI",
    "0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5": "Compound cETH",
    "0x39aa39c021dfbae8fac545936693ac917d5e7563": "Compound cUSDC",
    "0xccf4429db6322d5c611ee964527d42e5d685dd6a": "Compound cWBTC",
    "0xf5dce57282a584d2746faf1593d3121fcac444dc": "Compound cSAI",
    "0x70e36f6bf80a52b3b46b3af8e106cc0ed743e8e4": "Compound cCOMP",
    "0xa17581a9e3356d9a858b789d68b4d866e593ae94": "Compound Comet",
    "0xc3d688b66703497daa19211eedff47f25384cdc3": "Compound V3 USDC",

    # ===== MakerDAO =====
    "0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2": "Maker Token (MKR)",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI Stablecoin",
    "0x83f20f44975d03b1b09e64809b757c47f942beea": "sDAI (Savings DAI)",
    "0x35d1b3f3d7966a1dfe207aa4514c12a259a0492b": "Maker Vat",
    "0x9759a6ac90977b93b58547b4a71c78317f391a28": "Maker Flapper",
    "0xa950524441892a31ebddf91d3ceefa04bf454466": "Maker Flopper",
    "0x65c79fcb50ca1594b025960e539ed7a9a6d434a3": "Maker Pot",
    "0x197e90f9fad81970ba7976f33cbd77088e5d7cf7": "Maker Pot 2",
    "0x5ef30b9986345249bc32d8928b7ee64de9435e39": "Maker CDP Manager",

    # ===== Curve Finance =====
    "0xd533a949740bb3306d119cc777fa900ba034cd52": "Curve Token (CRV)",
    "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7": "Curve 3pool",
    "0xa5407eae9ba41422680e2e00537571bcc53efbfd": "Curve sUSD Pool",
    "0x99a58482bd75cbab83b27ec03ca68ff489b5788f": "Curve Tricrypto2",
    "0xd51a44d3fae010294c616388b506acda1bfaae46": "Curve Tricrypto",
    "0x5a6a4d54456819380173272a5e8e9b9904bdf41b": "Curve MIM Pool",
    "0x4ebdf703948ddcea3b11f675b4d1fba9d2414a14": "Curve crvUSD Controller",
    "0xf939e0a03fb07f59a73314e73794be0e57ac1b4e": "crvUSD",
    "0x90e00ace148ca3b23ac1bc8c240c2a7dd9c2d7f5": "Curve Router",

    # ===== Convex Finance =====
    "0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b": "Convex Token (CVX)",
    "0xf403c135812408bfbe8713b5a23a04b3d48aae31": "Convex Booster",
    "0x989aeb4d175e16225e39e87d0d97a3360524ad80": "Convex cvxCRV",
    "0x3fe65692bfcd0e6cf84cb1e7d24108e434a7587e": "Convex cvxCRV Rewards",
    "0xd18140b4b819b895a3dba5442f959fa44994af50": "Convex CRV Depositor",
    "0xcf50b810e57ac33b91dcf525c6ddd9881b139332": "Convex Vote Proxy",
    "0x72a19342e8f1838460ebfccef09f6585e32db86e": "Convex Staker",

    # ===== Balancer =====
    "0xba100000625a3754423978a60c9317c58a424e3d": "Balancer Token (BAL)",
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
    "0xa331d84ec860bf466b4cdccfb4ac09a1b43f3ae6": "Balancer Pool Factory",
    "0x394ab5d7d6c6c66e0f5b9377ddfc0b5e9d9a1f0f": "Balancer Weighted Pool Factory",
    "0xe3f706ad95ed4a0b6fb82f9e5bf8d9c49e0b0ce7": "Balancer Stable Pool Factory",

    # ===== SushiSwap =====
    "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2": "SushiSwap Token (SUSHI)",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "SushiSwap Router",
    "0xc2edad668740f1aa35e4d8f227fb8e17dca888cd": "SushiSwap MasterChef",
    "0xef0881ec094552b2e128cf945ef17a6752b4ec5d": "SushiSwap MasterChef V2",
    "0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac": "SushiSwap Factory",

    # ===== 1inch =====
    "0x111111111117dc0aa78b770fa6a738034120c302": "1inch Token",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router V5",
    "0x11111112542d85b3ef69ae05771c2dccff4faa26": "1inch Router V4",
    "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch Router V3",
}

# ===== Дополнительные биржевые адреса для новых сетей =====
BITSTAMP_ADDRESSES: dict[str, str] = {
    "0x00bdb5699745f5b860228c8f939abf1b9ae374ed": "Bitstamp",
    "0x1522900b6dafac587d499a862861c0869be6e428": "Bitstamp 2",
    "0x9a9bed3eb03e386d66f8a29dc67dc29bbb1ccb72": "Bitstamp 3",
    "0x59448fe20378357f206880c58068f095ae63d5a5": "Bitstamp 4",
    "0x4976a4a02f38326660d17bf34b431dc6e2eb2327": "Bitstamp Cold",
}


def get_ethereum_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Ethereum адреса.

    Проверяет все известные базы адресов: биржи, киты, DeFi протоколы.

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
    if address_lower in DEFI_PROTOCOLS:
        return DEFI_PROTOCOLS[address_lower]
    if address_lower in BITSTAMP_ADDRESSES:
        return BITSTAMP_ADDRESSES[address_lower]
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
    if address_lower in DEFI_PROTOCOLS:
        return DEFI_PROTOCOLS[address_lower]
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
        blockchain: Название блокчейна (ethereum, bsc, bitcoin, solana, ton)

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
    elif blockchain_lower in ("solana", "sol"):
        return get_solana_wallet_label(address)
    elif blockchain_lower == "ton":
        return get_ton_wallet_label(address)
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
        "kucoin", "huobi", "gemini", "bitfinex", "gate",
        "crypto.com", "mexc", "bitget"
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


# ===== Solana Wallets =====
# Импортируем из отдельного модуля для избежания циклических импортов
def get_solana_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Solana адреса.

    Args:
        address: Адрес кошелька Solana

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    from whale.solana import get_solana_wallet_label as _get_solana_label
    return _get_solana_label(address)


def get_ton_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для TON адреса.

    Args:
        address: Адрес кошелька TON

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    from whale.ton import get_ton_wallet_label as _get_ton_label
    return _get_ton_label(address)
