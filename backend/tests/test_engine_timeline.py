"""Buffs ativos no pull (poção, defensivo, Salvo montado): a luta só mostra a saída deles."""

from app.engine.timeline import buff_windows, initial_stacks, stack_gains, stacks_before

SALVO, POTION = 1242974, 1236616


def fight(buffs: list[tuple[int, str, float, int | None]], auras: list[dict] | None = None) -> dict:
    data = {
        "meta": {"fight": {"startTime": 1000, "endTime": 61000}},
        "player": {"actor": {"id": 10}},
        "events": {
            "buffs": [
                {"type": k, "abilityGameID": a, "timestamp": t, **({"stack": s} if s else {})}
                for a, k, t, s in buffs
            ]
        },
    }
    if auras is not None:
        data["player"]["combatant"] = {"stats": {}, "auras": auras}
    return data


def test_buff_removed_without_entry_was_active_since_the_pull():
    data = fight([(POTION, "removebuff", 28000, None), (POTION, "applybuff", 40000, None)])
    assert buff_windows(data, POTION) == [(1000, 28000), (40000, 61000)]


def test_buff_from_the_pull_auras_without_events_lasts_the_whole_fight():
    data = fight([], auras=[{"ability": POTION, "stacks": 1}])
    assert buff_windows(data, POTION) == [(1000, 61000)]


def test_buff_applied_in_the_fight_starts_inactive():
    data = fight([(POTION, "applybuff", 5000, None), (POTION, "removebuff", 35000, None)])
    assert initial_stacks(data, POTION) == 0
    assert buff_windows(data, POTION) == [(5000, 35000)]


def test_salvo_built_before_the_pull_keeps_its_stacks():
    """O primeiro removebuffstack para 7 diz que havia 8 no pull; ganho do pull não conta."""
    data = fight(
        [
            (SALVO, "removebuffstack", 3000, 7),
            (SALVO, "applybuffstack", 4000, 8),
            (SALVO, "removebuff", 5000, None),
        ]
    )
    assert initial_stacks(data, SALVO) == 8
    assert stacks_before(data, SALVO, [2000, 3500, 4500, 6000]) == [8, 7, 8, 0]
    assert stack_gains(data, SALVO) == 1


def test_pull_auras_give_the_stacks_when_the_first_event_is_the_exit():
    data = fight([(SALVO, "removebuff", 3000, None)], auras=[{"ability": SALVO, "stacks": 12}])
    assert stacks_before(data, SALVO, [2000]) == [12]
