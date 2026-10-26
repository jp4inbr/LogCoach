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

# Report inteiro numa consulta só (limite de 1000 pontos/h): lutas de chefe, jogadores e
# specs/item level. O playerDetails soma todas as lutas de chefe do report.
REPORT_FIGHTS = """
query ReportFights($code: String!) {
  reportData {
    report(code: $code) {
      code
      title
      fights(killType: Encounters) {
        id encounterID name difficulty kill startTime endTime friendlyPlayers
      }
      masterData {
        actors(type: "Player") { id name server type subType }
      }
      playerDetails(killType: Encounters)
    }
  }
}
"""
