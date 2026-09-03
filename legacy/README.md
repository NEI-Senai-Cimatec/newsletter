# Legacy

Arquivos mantidos apenas como referência histórica. Nenhum deles é importado ou carregado pelo código ativo do projeto.

- `sitemap.py`: versão anterior da lógica hoje em `thequantuminsider.py`. Não é importado por `run.py` nem por nenhum outro módulo.
- `parse_v3.txt` / `parse_v3.json`: versão anterior do template de prompt e do schema de validação da IA. `utils.py` carrega explicitamente `parse_v4.txt` e `parse_v4.json` (pasta `template/`).

Se precisar comparar o comportamento atual com uma versão anterior, esses arquivos servem de referência. Não é necessário mantê-los atualizados.
