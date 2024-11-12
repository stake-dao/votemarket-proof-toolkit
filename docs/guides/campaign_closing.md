## Campaign Closing

### Overview

> [!IMPORTANT]
> Campaign closing follows specific rules based on timing and who initiates the close. Understanding these scenarios is crucial for proper campaign management.

### Closing Scenarios

> [!NOTE]
> 1. **Before Campaign Start**
>    - Only campaign manager can close
>    - All rewards are returned to the manager
>    - No claims possible
>
> 2. **During Active Campaign**
>    - Closing is not possible
>    - Attempting to close will result in transaction revert
>
> 3. **During Close Window** (after claim period ends)
>    - Only campaign manager can close
>    - Unclaimed rewards are returned to manager
>    - Claims still possible until closure
>
> 4. **After Close Window**
>    - Anyone can initiate closure
>    - Unclaimed rewards go to fee collector
>    - No more claims possible

### Important Notes for L1 Tokens

> [!WARNING]
> When closing campaigns with wrapped tokens (L1 tokens bridged to L2):
>
> 1. **Token Reception**
>    - Wrapped tokens are received on L2 upon closure
>    - These are not the original L1 tokens
>
> 2. **Bridging Back to L1**
>    - Use the integrated Bridge (LaPoste) contract
>    - Wait for CCIP message processing on L1
>    - Consider gas costs for bridging in your strategy

### Timing Windows

> [!IMPORTANT]
> - Claim Window: 24 weeks after campaign end
> - Close Window: 4 weeks after campaign end
> - Use helper functions to check current status

> [!TIP]
> For implementation details and helper functions, see `close_campaign.py` in the `examples/` directory.