"""Consultas GraphQL usadas pelo LogCoach (fora a de eventos, que fica no client)."""

FIGHT_META = """
query FightMeta($code: String!, $fightID: Int!) {
  reportData {
    report(code: $code) {
      code
      startTime
      fights(fightIDs: [$fightID]) {
        id encounterID name difficulty kill size startTime endTime
        phaseTransitions { id startTime }
      }
      phases { encounterID phases { id name isIntermission } }
      masterData {
        actors { id name server type subType petOwner gameID }
        abilities { gameID name icon type }
      }
      playerDetails(fightIDs: [$fightID])
    }
  }
}
"""

ENCOUNTER_BRACKETS = """
query Brackets($encounterID: Int!) {
  worldData {
    encounter(id: $encounterID) {
      name
      zone { id name brackets { min max bucket type } }
    }
  }
}
"""

CHARACTER_RANKINGS = """
query Rankings(
  $encounterID: Int!, $className: String!, $specName: String!,
  $difficulty: Int!, $bracket: Int, $page: Int!
) {
  worldData {
    encounter(id: $encounterID) {
      characterRankings(
        className: $className, specName: $specName, difficulty: $difficulty,
        metric: dps, bracket: $bracket, page: $page
      )
    }
  }
}
"""

# Lista de lutas de chefe ao colar o link (1 ponto no report de referência): só o que decide
# se a luta é suportada. Nada de jogadores: o log pode ter o dia inteiro (outras raides,
# masmorras) e os Magos só são buscados na luta escolhida (FIGHT_PLAYERS).
REPORT_FIGHTS = """
query ReportFights($code: String!) {
  reportData {
    report(code: $code) {
      code
      title
      fights(killType: Encounters) {
        id encounterID name difficulty kill startTime endTime inProgress
      }
    }
  }
}
"""

# Magos de uma luta (2 pontos): spec e item level vêm da própria luta (friendlySpecs e
# friendlyItemLevels seguem a ordem de friendlyPlayers). Atores só os Magos do report.
# Conferido na API real em 28/10/2026 (tests/fixtures/fight_players_XhrmBaYkGCAQjH2D_34.json):
# as três listas têm o mesmo tamanho, spec em texto ("Arcane") e item level inteiro.
FIGHT_PLAYERS = """
query FightPlayers($code: String!, $fightID: Int!) {
  reportData {
    report(code: $code) {
      fights(fightIDs: [$fightID]) {
        id friendlyPlayers friendlySpecs friendlyItemLevels
      }
      masterData {
        actors(type: "Player", subType: "Mage") { id name server type subType }
      }
    }
  }
}
"""

# Reserva do FIGHT_PLAYERS quando a luta vem sem spec de algum jogador (1 ponto a mais).
FIGHT_PLAYER_DETAILS = """
query FightPlayerDetails($code: String!, $fightID: Int!) {
  reportData {
    report(code: $code) {
      playerDetails(fightIDs: [$fightID])
    }
  }
}
"""
