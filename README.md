# Tarefas Recebimentos Contencioso

Dashboard interativo em Streamlit para acompanhar entradas, conclusões e trabalho em aberto por tarefa e responsável.

## Funcionalidades

- Indicadores de stock total, concluídos, em tratamento, pendentes e taxa de conclusão.
- Tempo médio entre a entrada e a conclusão.
- Gráficos mensais, distribuição por estado e volume em aberto por tarefa.
- Entradas e conclusões anteriores a 2026 agrupadas num único período no gráfico mensal.
- Prefixo “DL” removido dos nomes das tarefas e “Pagamentos ilhas” apresentado como “Pgto Ilhas - via ficheiro”.
- Quadro de pendentes agrupado por tarefa, com antiguidade e exportação CSV.
- Separador de análise por responsável atribuído, com distribuição por estado, taxa de conclusão e tempo médio; os pendentes sem responsável ficam excluídos.
- Filtros por tarefa, responsável, período de entrada e descrição.
- Separadores próprios para pendentes, registos em tratamento e todos os registos.
- Exportação dos resultados filtrados para CSV.
- Carregamento de CSV ou Excel com várias folhas.
- Normalização dos utilizadores para minúsculas, sem diferenças de acentos ou espaços exteriores.

O ficheiro operacional `Quantidade_08.10.xlsx` é local e não é incluído no repositório. Carrega-o pela barra lateral para visualizar o dashboard; as folhas compatíveis são consolidadas na memória. Se existir uma cópia local em `data/stock_08_10.csv`, o dashboard também a utiliza automaticamente.

## Estados

- **Pendente:** sem responsável e sem data de tratamento.
- **Em tratamento:** tem responsável, mas ainda não tem data de tratamento.
- **Concluído:** tem data de tratamento.

## Executar

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Carrega o ficheiro de stock na barra lateral. Em Excel, as folhas com as colunas `Data entrada`, `Descrição`, `User` e `Data tratamento` são consolidadas automaticamente; a folha de origem passa a ser a tarefa. Em CSV, usa estas mesmas colunas e separa-as por vírgulas ou ponto e vírgula. Se o ficheiro incluir a coluna opcional `Tarefa`, é usada para identificar cada tipo de trabalho.

A interface usa as cores oficiais do sistema de design NOS — rosa `#EB84CD`, azul `#4F60D2`, ciano `#4BDBC5`, verde `#6EA514`, vermelho `#E04232`, amarelo `#FCD200` e lima `#BAD80A` — em conjunto com fundos neutros e suaves. Os valores vêm dos tokens públicos em [nos.pt](https://www.nos.pt/) e no [sistema de design Alma da NOS](https://cdn.nos.pt/alma-design-system/tokens/nos/dist/0.1.0/tokens.min.css).
