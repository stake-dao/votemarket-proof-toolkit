# TypeScript Integration Examples

These examples demonstrate how to integrate with the VoteMarket toolkit from TypeScript/JavaScript applications.

## Purpose

These TypeScript examples are provided as **reference implementations** to show:
- How CCIP gas estimation works in TypeScript
- Web3.js/Ethers.js integration patterns with VoteMarket contracts
- Alternative implementation approaches for developers using TypeScript

## Important Note

**The main VoteMarket toolkit is a Python SDK.** These TypeScript examples are not the primary SDK but serve as:
1. Reference implementations for TypeScript developers
2. Examples of direct contract interaction patterns
3. Alternative approaches for specific use cases

## Structure

```
typescript/
├── scripts/
│   └── estimate-ccip-gas.ts    # CCIP gas estimation example
├── types/
│   └── ccip.ts                 # TypeScript type definitions
└── utils/
    └── ccip.ts                 # CCIP utility functions
```

## Installation

```bash
# From this directory
npm install
# or
pnpm install
```

## Usage Examples

### CCIP Gas Estimation

```bash
# Run the CCIP gas estimation script
npm run simulate -- \
  --adapter 0xYourAdapterAddress \
  --laposte 0xYourLaPosteAddress \
  --to 0xRecipientAddress \
  --tokens 0xToken1:1000000,0xToken2:2000000
```

### Using as Reference

These examples show direct contract interaction. You can:
1. Copy relevant code snippets into your TypeScript project
2. Use the type definitions for your own implementations
3. Reference the utility functions for contract calls

## Comparison with Python SDK

| Feature | Python SDK | TypeScript Examples |
|---------|------------|-------------------|
| Status | Main SDK | Reference only |
| Published | Yes (PyPI) | No (examples) |
| Maintained | Actively | As needed |
| Purpose | Full toolkit | Integration examples |

## For Python SDK Users

If you're using the main Python SDK and need TypeScript integration:
1. Use these examples as a reference for contract ABIs and types
2. Consider calling the Python SDK from Node.js via child processes
3. Use the type definitions to ensure compatibility

## Contributing

When contributing TypeScript examples:
- Focus on demonstrating integration patterns
- Keep examples self-contained and well-documented
- Ensure compatibility with the main Python SDK's functionality