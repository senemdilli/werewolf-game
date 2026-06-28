from wolf_llm_labeling.contexts import (
    ContextProvider,
    JoinedContext,
    StaticContext,
    GameNowContext,
    PhaseGameContext,
    PhaseTrustContext,
)
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.models import PlayerName, LLMModelProviders


def experiment(
    player_name: PlayerName,
    args: str,
    models: LLMModelProviders,
) -> tuple[ContextProvider, InnerVoice | None]:
    cutoff = int(args.strip()) if args.strip() else 0
    # Base context: Game static + Game now
    base_ctx = JoinedContext('Game Information', None, 1000, StaticContext(player_name), GameNowContext(player_name))
    
    # Historical phases: game data and trust scores
    game_history = [PhaseGameContext(i) for i in range(1, cutoff)]
    trust_history = [PhaseTrustContext(i) for i in range(1, cutoff)]
    
    history_elements = game_history + trust_history
    
    if history_elements:
        history_ctx = JoinedContext('Historical Game History', None, 0, *history_elements)
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0), history_ctx)
    else:
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0))
        
    return (ctx, None)
