export interface TokenMetadata {
  name: string;
  symbol: string;
  decimals: number;
}

export interface TokenTransfer {
  token: string;
  symbol: string;
  amount: number;
  rawAmount: bigint;
}

export interface TransferDetails {
  toAddress: string;
  chainId: number;
  sender: string;
  transfers: TokenTransfer[];
  nonce: number;
}

export interface GasEstimation {
  baseGas: number;
  gasWithBuffer: number;
  ccipFee: bigint;
}

export interface CCIPMessage {
  receiver: string;
  data: string;
  tokenAmounts: any[];
  feeToken: string;
  extraArgs: string;
}

export interface Any2EVMMessage {
  messageId: string;
  sourceChainSelector: number;
  sender: string;
  data: string;
  destTokenAmounts: {
    token: string;
    amount: bigint;
  }[];
} 