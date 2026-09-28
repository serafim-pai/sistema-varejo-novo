# 🧱 Sistema de Varejo — Material de Construção

Sistema simples de **estoque e vendas** para uma loja de material de construção.
Projeto criado para praticar **Python, Git, GitHub, Claude e Scrum**.

## ✅ O que o sistema faz

1. **Cadastro de produtos**: nome, preço, quantidade e categoria.
2. **Registro de vendas**: o estoque diminui sozinho a cada venda.
3. **Histórico de vendas**: mostra o que foi vendido, a quantidade, o valor e a data.
4. **Relatórios**: total de produtos, valor em estoque e ranking dos **produtos mais vendidos**.
5. **Proteção**: não deixa vender mais do que existe no estoque.
6. **Editar produtos**: corrige nome, preço, quantidade ou categoria de um produto já cadastrado.
7. **Validações no cadastro**: não aceita nome ou categoria vazios, preço zero ou negativo, nem quantidade negativa.

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
- [ ] Melhorar a aparência das telas

## 👤 Autor

**serafim-pai**, aprendendo programação um passo de cada vez.
