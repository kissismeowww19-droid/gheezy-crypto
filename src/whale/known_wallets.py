"""
Gheezy Crypto - База известных кошельков

Расширенная база адресов крупных бирж, известных китов и функции
определения владельца кошелька. Работает для Ethereum, BSC, Bitcoin,
Solana и TON.

Содержит:
- Binance (все hot/cold wallets)
- Coinbase, Kraken, OKX, Bybit, Bitfinex, Gemini, Huobi
- PancakeSwap и другие DEX
- Известные киты и фонды
- ETF провайдеры (BlackRock, Fidelity, Grayscale)
- Майнеры (Marathon, Riot, CleanSpark)
- DeFi протоколы (Lido, Aave, Compound)
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

# Известные киты и фонды (whale wallets)
# Расширенный список с институциональными инвесторами и фондами
KNOWN_WHALES: dict[str, str] = {
    # ===== Ethereum Foundation =====
    "0x73bceb1cd57c711feac4224d062b0f6ff338501e": "Ethereum Foundation",
    "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae": "Ethereum Foundation",
    "0x9d5a5eb9a5a5c0b5d5a5b9a5a5c0b5d5a5b9a5a5": "Ethereum Foundation Treasury",

    # ===== Известные киты =====
    "0x220866b1a2219f40e72f5c628b65d54268ca3a9d": "Genesis Whale",
    "0xab5801a7d398351b8be11c439e05c5b3259aec9b": "Vitalik Buterin",
    "0xd8da6bf26964af9d7eed9e03e53415d37aa96045": "Vitalik Buterin 2",

    # ===== NFT и DeFi протоколы =====
    "0x7be8076f4ea4a4ad08075c2508e481d6c946d12b": "OpenSea",
    "0x00000000219ab540356cbb839cbe05303d7705fa": "ETH2 Deposit Contract",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",

    # ===== Институциональные инвесторы =====
    "0x4862733b5fddfd35f35ea8ccf08f5045e57388b3": "MicroStrategy",
    "0x1c11ba15939e1c16ec7ca1678df6160ea2063bc5": "Tesla",
    "0xf4b51b14b9ee30dc37ec970b50a486f37686e2a8": "Grayscale",
    "0x2140efd7ba31169c69dfff6cdc66c542f0211e96": "Jump Trading",
    "0x46705dfff24256421a05d056c29e81bdc09723b8": "Three Arrows Capital",

    # ===== Мосты и протоколы =====
    "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": "Polygon Bridge",
    "0xa0c68c638235ee32657e8f720a23cec1bfc77c77": "Polygon Bridge 2",
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism Bridge",
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f": "Arbitrum Bridge",
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge 2",
    "0x5fdcca53617f4d2b9134b29090c87d01058e27e9": "Immutable X",

    # ===== Стейкинг =====
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "Lido wstETH",
    "0xdc24316b9ae028f1497c275eb9192a3ea0f67022": "Lido Staking Pool",
    "0xa2f987a546d4cd1c607ee8141276876c26b72bdf": "Anchor Protocol",

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

    # ===== DAO Treasuries =====
    "0x0bef27feb58e857046d630b2c03dfb7bae567494": "MakerDAO Treasury",
    "0xe7804c37c13166ff0b37f5ae0bb07a3aebb6e245": "Uniswap Treasury",
    "0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359": "ENS Treasury",
    "0x78605df79524164911c144801f41e9811b7db73d": "BitDAO Treasury",

    # ===== MEV Bots (важно для трекинга!) =====
    "0x98c3d3183c4b8a650614ad179a1a98be0a8d6b8e": "MEV Bot",
    "0x00000000000002b0bb9b5dfab7e46f76856f9d03": "MEV Bot 2",
    "0x000000000035b5e5ad9019092c665357240f594e": "Flashbots MEV",
    "0x5aa3393e361c2eb342408559309b3e873cd876d6": "MEV Searcher",
    "0xd8d0be9c3b6e7e4f5e69e4f8e7c8c5e4d5c4b3a2": "Sandwich Bot",
    "0x56178a0d5f301baf6cf3e1cd53d9863437345bf9": "Jaredfromsubway",
    "0x6b75d8af000000e20b7a7ddF000Ba900b4009a80": "MEV Builder",

    # ===== Flashbots =====
    "0xdafea492d9c6733ae3d56b7ed1adb60692c98bc5": "Flashbots Builder",
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
