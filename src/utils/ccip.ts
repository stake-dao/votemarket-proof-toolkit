import { ethers } from 'ethers';
import { TokenMetadata, TokenTransfer, TransferDetails, GasEstimation, CCIPMessage, Any2EVMMessage } from '../types/ccip';

// ABIs
const ERC20_ABI = [
  { constant: true, inputs: [], name: 'name', outputs: [{ name: '', type: 'string' }], type: 'function' },
  { constant: true, inputs: [], name: 'symbol', outputs: [{ name: '', type: 'string' }], type: 'function' },
  { constant: true, inputs: [], name: 'decimals', outputs: [{ name: '', type: 'uint8' }], type: 'function' }
];

const TOKEN_FACTORY_ABI = [
  {
    inputs: [{ name: 'token', type: 'address' }],
    name: 'wrappedTokens',
    outputs: [{ name: '', type: 'address' }],
    type: 'function',
    stateMutability: 'view'
  }
];

const BALANCE_ABI = [
  {
    constant: true,
    inputs: [{ name: 'account', type: 'address' }],
    name: 'balanceOf',
    outputs: [{ name: '', type: 'uint256' }],
    type: 'function'
  }
];

const LAPOSTE_ABI = [
  {
    inputs: [{ name: 'chainId', type: 'uint256' }],
    name: 'sentNonces',
    outputs: [{ name: '', type: 'uint256' }],
    type: 'function',
    stateMutability: 'view'
  }
];

const ADAPTER_ABI = [
  {
    inputs: [{ name: 'chainId', type: 'uint256' }],
    name: 'getBridgeChainId',
    outputs: [{ name: '', type: 'uint64' }],
    type: 'function',
    stateMutability: 'view'
  }
];

// Default token factory address
const DEFAULT_TOKEN_FACTORY = '0x96006425Da428E45c282008b00004a00002B345e';

export async function getWrappedToken(
  tokenAddress: string,
  tokenFactoryAddress: string,
  provider: ethers.providers.Provider
): Promise<string> {
  try {
    const factory = new ethers.Contract(tokenFactoryAddress, TOKEN_FACTORY_ABI, provider);
    const wrappedToken = await factory.wrappedTokens(tokenAddress);
    return wrappedToken;
  } catch (error) {
    console.error(`Error getting wrapped token for ${tokenAddress}:`, error);
    throw error;
  }
}

export async function getTokenBalance(
  tokenAddress: string,
  holderAddress: string,
  provider: ethers.providers.Provider
): Promise<bigint> {
  try {
    const token = new ethers.Contract(tokenAddress, BALANCE_ABI, provider);
    const balance = await token.balanceOf(holderAddress);
    return BigInt(balance.toString());
  } catch (error) {
    console.error(`Error getting balance for token ${tokenAddress}:`, error);
    throw error;
  }
}

export async function fetchTokenMetadata(
  tokenAddress: string,
  provider: ethers.providers.Provider
): Promise<TokenMetadata> {
  try {
    const contract = new ethers.Contract(tokenAddress, ERC20_ABI, provider);
    const [name, symbol, decimals] = await Promise.all([
      contract.name(),
      contract.symbol(),
      contract.decimals()
    ]);
    return { name, symbol, decimals };
  } catch (error) {
    console.error(`Error fetching metadata for token ${tokenAddress}:`, error);
    return { name: 'Unknown', symbol: '???', decimals: 18 };
  }
}

export async function getChainSelector(
  adapterAddress: string,
  chainId: number,
  provider: ethers.providers.Provider
): Promise<number> {
  try {
    const contract = new ethers.Contract(adapterAddress, ADAPTER_ABI, provider);
    const selector = await contract.getBridgeChainId(chainId);
    console.log(`Chain selector for chain ID ${chainId}: ${selector}`);
    return selector;
  } catch (error) {
    console.error('Error getting chain selector:', error);
    throw error;
  }
}

export async function getNextNonce(
  laposteAddress: string,
  destinationChainId: number,
  provider: ethers.providers.Provider
): Promise<number> {
  try {
    const contract = new ethers.Contract(laposteAddress, LAPOSTE_ABI, provider);
    const currentNonce = await contract.sentNonces(destinationChainId);
    return currentNonce.toNumber() + 1;
  } catch (error) {
    console.error('Error getting nonce:', error);
    throw error;
  }
}

export async function createLaposteMessage(
  destinationChainId: number,
  toAddress: string,
  senderAddress: string,
  tokens: [string, bigint][],
  nonce: number,
  provider: ethers.providers.Provider,
  payload: string = '0x'
): Promise<{ message: string; details: TransferDetails }> {
  const tokenMetadata: TokenMetadata[] = [];
  const transferSummary: TokenTransfer[] = [];

  for (const [tokenAddress, amount] of tokens) {
    const metadata = await fetchTokenMetadata(tokenAddress, provider);
    tokenMetadata.push(metadata);

    const humanAmount = Number(amount) / Math.pow(10, metadata.decimals);
    transferSummary.push({
      token: tokenAddress,
      symbol: metadata.symbol,
      amount: humanAmount,
      rawAmount: amount
    });
  }

  const messageTuple = [
    destinationChainId,
    toAddress,
    senderAddress,
    tokens,
    tokenMetadata.map(m => [m.name, m.symbol, m.decimals]),
    payload,
    nonce
  ];

  const transferDetails: TransferDetails = {
    toAddress,
    chainId: destinationChainId,
    sender: senderAddress,
    transfers: transferSummary,
    nonce
  };

  const types = ['tuple(uint256,address,address,tuple(address,uint256)[],tuple(string,string,uint8)[],bytes,uint256)'];
  const message = ethers.utils.defaultAbiCoder.encode(types, [messageTuple]);

  return { message, details: transferDetails };
}

export async function estimateCcipFee(
  routerAddress: string,
  adapterAddress: string,
  destinationChainSelector: number,
  message: string,
  gasLimit: number,
  provider: ethers.providers.Provider
): Promise<bigint> {
  try {
    const routerAbi = ['function getFee(uint64 destinationChainSelector, tuple(bytes receiver, bytes data, tuple(address token, uint256 amount)[] tokenAmounts, address feeToken, bytes extraArgs) message) view returns (uint256)'];
    const routerContract = new ethers.Contract(routerAddress, routerAbi, provider);

    const EVM_EXTRA_ARGS_V1_TAG = '0x97a657c9';
    const extraArgsData = ethers.utils.defaultAbiCoder.encode(['uint256'], [gasLimit]);
    const evmExtraArgs = EVM_EXTRA_ARGS_V1_TAG + extraArgsData.slice(2);

    const ccipMessage: CCIPMessage = {
      receiver: ethers.utils.defaultAbiCoder.encode(['address'], [adapterAddress]),
      data: message,
      tokenAmounts: [],
      feeToken: ethers.constants.AddressZero,
      extraArgs: evmExtraArgs
    };

    const fee = await routerContract.getFee(destinationChainSelector, ccipMessage);
    return BigInt(fee.toString()) * BigInt(102) / BigInt(100); // Add 2% buffer
  } catch (error) {
    console.error('Fee estimation failed:', error);
    throw error;
  }
}

export async function simulateCcipReceive(
  adapterAddress: string,
  laposteAddress: string,
  toAddress: string,
  tokens: [string, bigint][],
  sourceProvider: ethers.providers.Provider,
  destProvider: ethers.providers.Provider
): Promise<GasEstimation> {
  const ARBITRUM_CHAIN_ID = 42161;
  const ETHEREUM_CHAIN_ID = 1;

  const sourceChainSelector = await getChainSelector(adapterAddress, ARBITRUM_CHAIN_ID, destProvider);
  const destinationChainSelector = await getChainSelector(adapterAddress, ETHEREUM_CHAIN_ID, sourceProvider);
  const nonce = await getNextNonce(laposteAddress, ETHEREUM_CHAIN_ID, sourceProvider);

  const { message } = await createLaposteMessage(
    ETHEREUM_CHAIN_ID,
    toAddress,
    laposteAddress,
    tokens,
    nonce,
    destProvider
  );

  const any2EvmMessage: Any2EVMMessage = {
    messageId: ethers.utils.id('test'),
    sourceChainSelector,
    sender: ethers.utils.defaultAbiCoder.encode(['address'], [laposteAddress]),
    data: message,
    destTokenAmounts: []
  };

  const ccipReceiveInterface = new ethers.utils.Interface([
    'function ccipReceive((bytes32 messageId, uint64 sourceChainSelector, bytes sender, bytes data, tuple(address token, uint256 amount)[] destTokenAmounts)) external'
  ]);

  const data = ccipReceiveInterface.encodeFunctionData('ccipReceive', [any2EvmMessage]);
  const DESTINATION_ROUTER_ADDRESS = '0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D'; // Ethereum Router

  try {
    const gas = await destProvider.estimateGas({
      from: DESTINATION_ROUTER_ADDRESS,
      to: adapterAddress,
      data
    });

    const baseGas = gas.toNumber() - 50000;
    const gasWithBuffer = Math.floor(baseGas * 1.077);
    const totalGasLimit = gasWithBuffer + 50000;

    const SOURCE_ROUTER_ADDRESS = '0x141fa059441E0ca23ce184B6A78bafD2A517DdE8'; // Arbitrum Router
    const ccipFee = await estimateCcipFee(
      SOURCE_ROUTER_ADDRESS,
      adapterAddress,
      destinationChainSelector,
      message,
      totalGasLimit,
      sourceProvider
    );

    return {
      baseGas,
      gasWithBuffer,
      ccipFee
    };
  } catch (error) {
    console.error('Gas estimation failed:', error);
    throw error;
  }
} 