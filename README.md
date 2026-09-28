# 🧱 Sistema de Varejo — Material de Construção

Sistema simples de **estoque e vendas** para uma loja de material de construção.
Projeto criado para praticar **Python, Git, GitHub, Claude e Scrum**.

## ✅ O que o sistema faz

### 📦 Produtos
1. **Cadastro de produtos**: nome, preço, quantidade, categoria e **unidade de medida** (UN, SACO, M³, M², M, KG, MILHEIRO, LATA, CAIXA, BARRA, ROLO, LITRO).
2. **Editar produtos**: corrige nome, preço, quantidade ou categoria de um produto já cadastrado.
3. **Excluir produtos**, com confirmação antes de apagar.
4. **+ Entrada (repor estoque)**: registra a chegada de mercadoria e soma ao estoque.
5. **Aviso de reposição**: no alto da tela, lista os produtos com estoque baixo 🟡 ou zerado 🔴.
6. **Validações**: não aceita nome ou categoria vazios ou com menos de 2 letras, preço zero ou negativo, nem quantidade negativa.

### 🛒 Vendas
7. **Carrinho de compras**: adicione vários produtos (ex.: 2 AREIA + 5 CIMENTO + 1 BRITA), veja o total e finalize tudo de uma vez.
8. **Comprovante para imprimir**: após finalizar, mostra o comprovante com itens, preços e total, pronto para imprimir.
9. **Busca por digitação**: digite parte do nome (ex.: "cim") e escolha o produto na lista.
10. **Caixa de estoque**: ao escolher o produto, uma caixa ao lado mostra quanto ainda tem em estoque.
11. **Baixa automática**: o estoque diminui sozinho a cada venda.
12. **Proteção**: não deixa vender mais do que existe no estoque.
13. **Histórico de vendas**: mostra o que foi vendido, a quantidade, o valor e a data.
14. **Cancelar venda**: desfaz uma venda errada e devolve os produtos ao estoque.
15. **Tecla Enter**: agiliza o cadastro e a venda sem precisar clicar nos botões.

### 📊 Relatórios
16. **Resumo do estoque**: total de produtos e valor total em estoque.
17. **Produtos mais vendidos**: ranking com unidades, número de vendas e valor vendido.

### 🎨 Visual
18. **Cores no estoque**:
    - 🟢 **Verde**: estoque bom (10 ou mais)
    - 🟡 **Amarelo**: estoque baixo (1 a 9)
    - 🔴 **Vermelho com bolinha**: sem estoque (0)
19. **Menu laranja em destaque**, mostrando a tela atual.

## 🛠️ Tecnologias usadas

- **Python** com **Flask** (o servidor do sistema)
- **SQLAlchemy** com **SQLite** (o banco de dados)
- **HTML, CSS e JavaScript** (as telas)

## 📁 Arquivos do projeto

```
sistema-varejo-novo/
├── app.py              → programa principal (rotas e telas)
├── database.py         → banco de dados (produtos e vendas)
├── requirements.txt    → bibliotecas necessárias
└── templates/
    ├── index.html      → tela de cadastro de produtos
    ├── vendas.html     → tela de vendas e histórico
    └── relatorios.html → tela de relatórios
```

## ▶️ Como rodar no computador

1. Instale as bibliotecas:
   ```
   pip install -r requirements.txt
   ```
2. Ligue o sistema:
   ```
   python app.py
   ```
3. No navegador, abra: `http://localhost:5000`

## 🚀 Próximos passos

- [x] Não aceitar campos vazios nem números negativos
- [x] Mostrar no relatório qual produto mais vende
- [x] Editar produtos
- [x] Busca de produto por digitação na venda
- [x] Cores e bolinha vermelha no estoque
- [x] Menu destacado
- [x] Repor estoque, aviso de reposição, cancelar venda e tecla Enter
- [x] Carrinho com vários produtos e comprovante para imprimir
- [x] Unidade de medida nos produtos, no carrinho e no comprovante
- [ ] Novas melhorias sugeridas pelo usuário

## 👤 Autor

**serafim-pai**, aprendendo programação um passo de cada vez.
