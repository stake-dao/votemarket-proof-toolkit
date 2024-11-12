# VoteMarket V2 Integration Guide

This guide is designed to help developers integrate and migrate their applications to the new VoteMarket V2 architecture. The new version introduces some changes in interaction with the platform, due to native cross-chain operations.

## Contents

- [VoteMarket V2 Integration Guide](#votemarket-v2-integration-guide)
  - [Contents](#contents)
  - [Quick Reference](#quick-reference)
    - [Contract Addresses \& Deployments](#contract-addresses--deployments)
  - [Campaign Creation](#campaign-creation)
  - [Campaign Management](#campaign-management)
  - [Campaign Closing](#campaign-closing)
  - [Claiming Campaign Rewards](#claiming-campaign-rewards)

## Quick Reference

### Contract Addresses & Deployments

| Contract              | Networks                                    | Address                                    |
|----------------------|---------------------------------------------|--------------------------------------------| 
| CampaignRemoteManager| Ethereum, Arbitrum, Base, Optimism, Polygon | `0xd1f0101Df22Cb7447F486Da5784237AB7a55eB4e` |
| CCIP Adapter         | Ethereum, Arbitrum, Base, Optimism, Polygon | `0x4200740090f72e89302f001da5860000007d7ea7` |
| VoteMarket           | Arbitrum, Base, Optimism, Polygon          | `0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5` |
| ORACLE               | Arbitrum, Base, Optimism, Polygon          | `0x36F5B50D70df3D3E1c7E1BAf06c32119408Ef7D8` |
| PROOF_VERIFIER       | Arbitrum, Base, Optimism, Polygon          | `0x2Fa15A44eC5737077a747ed93e4eBD5b4960a465` |

## Campaign Creation

- [L1 Token Campaigns (Ethereum → Arbitrum)](guides/campaign_creation.md#l1-token-campaigns-ethereum-arbitrum)
- [L2 Token Campaigns (Native Arbitrum)](guides/campaign_creation.md#l2-token-campaigns-native-arbitrum)

## Campaign Management

- [Update Campaign Epoch](guides/campaign_management.md#update-campaign-epoch)
- [From L1](guides/campaign_management.md#from-l1)
- [From L2](guides/campaign_management.md#from-l2)

## Campaign Closing

- [Overview](guides/campaign_management.md#campaign-closing)

## Claiming Campaign Rewards

- [Storage Proofs](guides/claiming_rewards.md#storage-proofs)