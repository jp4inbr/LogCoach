"""Buffs ativos no pull (poção, defensivo, Mirror Image): a luta só mostra a saída deles."""

from app.engine.timeline import buff_windows, initial_stacks, stack_gains, stacks_before

SALVO, POTION, CLEARCASTING = 1242974, 1236616, 263725


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


def test_first_stack_drop_gives_the_exact_stacks():
    """Clearcasting cai de uma em uma: o primeiro removebuffstack para 1 diz que havia 2."""
    data = fight(
        [
            (CLEARCASTING, "removebuffstack", 3000, 1),
            (CLEARCASTING, "applybuffstack", 4000, 2),
            (CLEARCASTING, "removebuff", 5000, None),
        ]
    )
    assert initial_stacks(data, CLEARCASTING) == 2
    assert stacks_before(data, CLEARCASTING, [2000, 3500, 4500, 6000]) == [2, 1, 2, 0]
    assert stack_gains(data, CLEARCASTING) == 1  # a carga do pull não conta


def test_pull_aura_beats_a_first_stack_gain():
    """O Salvo sobe até 9 de uma vez: com a aura do pull (10), um applybuffstack para 13 não
    quer dizer que havia 12."""
    data = fight([(SALVO, "applybuffstack", 3000, 13)], auras=[{"ability": SALVO, "stacks": 10}])
    assert initial_stacks(data, SALVO) == 10
    assert initial_stacks(fight([(SALVO, "applybuffstack", 3000, 13)]), SALVO) == 12


def test_first_applybuff_means_inactive_even_with_a_pull_aura():
    """Poção clicada no ms do pull e listada nas auras: o applybuff diz que ela entrou ali."""
    data = fight(
        [(POTION, "applybuff", 1000, None), (POTION, "removebuff", 31000, None)],
        auras=[{"ability": POTION, "stacks": 1}],
    )
    assert initial_stacks(data, POTION) == 0
    assert buff_windows(data, POTION) == [(1000, 31000)]


def test_refresh_without_entry_was_active_since_the_pull():
    data = fight([(POTION, "refreshbuff", 9000, None), (POTION, "removebuff", 20000, None)])
    assert buff_windows(data, POTION) == [(1000, 20000)]
