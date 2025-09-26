# VoteMarket Toolkit Examples

This directory contains usage examples for the VoteMarket toolkit in different programming languages.

## Structure

- **`python/`** - Python examples showing SDK usage
  - Direct SDK usage examples
  - Integration patterns
  - Common use cases

- **`typescript/`** - TypeScript reference implementations
  - CCIP gas estimation example
  - Contract interaction patterns
  - Web3.js/Ethers.js integration
  - **Note:** These are reference examples only. The main SDK is Python-based.

## Quick Start

### Python Examples

```bash
cd python
python get_campaign.py
python using_registry.py
```

### TypeScript Reference Examples

```bash
cd typescript
npm install
npm run simulate -- --adapter 0x... --laposte 0x... --to 0x...
```

## Purpose

- **Python examples**: Show how to use the main SDK
- **TypeScript examples**: Provide reference implementations for TypeScript developers who need to:
  - Understand contract interaction patterns
  - Implement similar functionality in TypeScript
  - Integrate with the Python SDK from Node.js applications

## Contributing

When adding examples:
1. Keep them self-contained and well-documented
2. Include clear comments explaining each step
3. Add error handling and edge cases
4. Update this README with new examples