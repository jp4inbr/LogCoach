# Fixtures dos testes do frontend

Respostas reais da API do backend no modo exemplo (`DATA_SOURCE=exemplo`, sem o
`names.local.json`: os tops saem só com pseudônimo, `top01`…`top10`), para o kill de
referência (report `XhrmBaYkGCAQjH2D`, luta 34, Harmonist):

- `report.json`: `POST /reports/resolve`
- `players.json`: `GET /reports/XhrmBaYkGCAQjH2D/fights/34/players`
- `analysis.json`: `POST /analyses` (resultado do motor, item 12.9)

Para gerar de novo depois de mudar o contrato: subir o backend no modo exemplo com um
banco SQLite temporário e salvar as três respostas aqui. Nunca colocar nomes reais.
