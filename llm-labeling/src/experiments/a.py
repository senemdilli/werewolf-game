from ..wolf_llm_labeling.contexts import *
from ..wolf_llm_labeling.inner_voice import *

def experiment_a(player_name: PlayerName, cutoff: int) -> tuple[ContextProvider, InnerVoice | None]:
    ctx = JoinedContext('Game Information', None, 1000, StaticContext(player_name), GameNowContext())
    ctx = JoinedContext(None, None, 0, ctx, PhaseGameContext(), 
        JoinedContext('Historical Game History', None, 0, *[PhaseGameContext(i) for i in range(1, 3*6)]))
    return (ctx, None)
