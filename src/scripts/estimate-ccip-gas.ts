import { ethers } from 'ethers';
import { simulateCcipReceive, getWrappedToken, getTokenBalance } from '../utils/ccip';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

// Configure environment variables
const ARBITRUM_RPC = process.env.ARBITRUM_MAINNET_RPC_URL || 'https://arb1.arbitrum.io/rpc';
const ETHEREUM_RPC = process.env.ETHEREUM_MAINNET_RPC_URL || 'https://eth.llamarpc.com';
const DEFAULT_TOKEN_FACTORY = '0x96006425Da428E45c282008b00004a00002B345e';

function validateAddress(address: string): string {
  try {
    return ethers.utils.getAddress(address.trim());
  } catch (error) {
    throw new Error(`Invalid address: ${address}`);
  }
}

async function getTokenWithBalance(
  tokenAddress: string,
  tokenFactoryAddress: string,
  toAddress: string,
  provider: ethers.providers.Provider
): Promise<[string, bigint]> {
  try {
    const wrappedToken = await getWrappedToken(tokenAddress, tokenFactoryAddress, provider);
    const balance = await getTokenBalance(wrappedToken, toAddress, provider);
    return [tokenAddress, balance];
  } catch (error) {
    try {
      const balance = await getTokenBalance(tokenAddress, toAddress, provider);
      return [tokenAddress, balance];
    } catch (balanceError) {
      return [tokenAddress, BigInt(0)];
    }
  }
}

async function main() {
  const argv = await yargs(hideBin(process.argv))
    .option('adapter', {
      type: 'string',
      description: 'Adapter contract address',
      required: true
    })
    .option('laposte', {
      type: 'string',
      description: 'LaPoste contract address',
      required: true
    })
    .option('to-address', {
      type: 'string',
      description: 'Recipient address',
      required: true
    })
    .option('tokens', {
      type: 'array',
      description: 'List of token addresses',
      required: true,
      string: true
    })
    .option('token-factory', {
      type: 'string',
      description: 'Token factory address',
      default: DEFAULT_TOKEN_FACTORY
    })
    .help()
    .argv;

  try {
    const sourceProvider = new ethers.providers.JsonRpcProvider(ARBITRUM_RPC);
    const destProvider = new ethers.providers.JsonRpcProvider(ETHEREUM_RPC);

    const adapterAddress = validateAddress(argv.adapter as string);
    const laposteAddress = validateAddress(argv.laposte as string);
    const toAddress = validateAddress(argv['to-address'] as string);
    const tokenFactoryAddress = validateAddress(argv['token-factory'] as string);

    if (!Array.isArray(argv.tokens)) {
      throw new Error('Tokens must be provided as an array');
    }

    const tokenAddresses = argv.tokens.map(token => {
      if (typeof token !== 'string') {
        throw new Error(`Invalid token address format: ${token}`);
      }
      return validateAddress(token);
    });

    const tokens: [string, bigint][] = await Promise.all(
      tokenAddresses.map(tokenAddress => 
        getTokenWithBalance(tokenAddress, tokenFactoryAddress, toAddress, sourceProvider)
      )
    );

    const estimation = await simulateCcipReceive(
      adapterAddress,
      laposteAddress,
      toAddress,
      tokens,
      sourceProvider,
      destProvider
    );

    console.log('=== Gas Estimation ===');
    console.log(`Base gas: ${estimation.baseGas.toLocaleString()}`);
    console.log(`Gas with 7.7% buffer: ${estimation.gasWithBuffer.toLocaleString()}`);
    console.log(`CCIP Fee: ${ethers.utils.formatEther(estimation.ccipFee)} ETH`);

  } catch (error) {
    if (error instanceof Error) {
      console.error('Error:', error.message);
    } else {
      console.error('Unknown error:', error);
    }
    process.exit(1);
  }
}

main().catch(error => {
  console.error('Error:', error);
  process.exit(1);
}); 