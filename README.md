# 🧱 Sistema de Varejo — Material de Construção

Sistema simples de **estoque e vendas** para uma loja de material de construção.
Projeto criado para praticar **Python, Git, GitHub, Claude e Scrum**.

## ✅ O que o sistema faz

### 🔐 Login e Usuários
1. **Entrar com e-mail e senha**: ninguém usa o sistema sem fazer login. As senhas são guardadas de forma protegida (nunca "abertas").
2. **Primeiro acesso**: na primeira vez que o sistema é aberto, ele pede para criar o **ADMINISTRADOR MASTER**.
3. **Dois tipos de usuário**:
    - 👑 **Administrador master**: pode tudo (produtos, preço de compra, relatórios, usuários e cancelar vendas).
    - 🧾 **Simples (balcão)**: faz vendas e orçamentos e consulta os produtos. Não vê preço de compra, nem a %, nem os relatórios.
4. **Tela de Usuários** (só o administrador): criar, editar, trocar senha, **bloquear/desbloquear** e excluir usuários.
5. **Proteções**: o administrador não consegue excluir nem tirar o próprio acesso; e-mail repetido não é aceito; senha com pelo menos 6 caracteres.
6. **Login sem sugestões do navegador**: a tela de login não oferece nem guarda e-mails e senhas no computador (bom para o terminal do balcão, que várias pessoas usam).
7. **Menu com o nome de quem está usando**, a etiqueta ADMINISTRADOR ou BALCÃO e o botão **Sair**.

### 📦 Produtos
8. **Cadastro de produtos**: nome, preço, quantidade, categoria e **unidade de medida** (UN, SACO, M³, M², M, KG, MILHEIRO, LATA, CAIXA, BARRA, ROLO, LITRO).
9. **Preço de compra → % de lucro → Preço de venda** (só o administrador): Digitou a compra e a %, o preço de venda é calculado sozinho; mudou o preço de venda, a % é recalculada. No terminal do balcão esses números **nem chegam** à tela.
10. **Editar produtos**: corrige nome, preço, quantidade ou categoria de um produto já cadastrado.
11. **Excluir produtos**, com confirmação antes de apagar.
12. **+ Entrada (repor estoque)**: registra a chegada de mercadoria e soma ao estoque.
13. **Aviso de reposição**: no alto da tela, lista os produtos com estoque baixo 🟡 ou zerado 🔴.
14. **Validações**: não aceita nome ou categoria vazios ou com menos de 2 letras, preço zero ou negativo, nem quantidade negativa.

### 🛒 Vendas
15. **Carrinho de compras**: adicione vários produtos (ex.: 2 AREIA + 5 CIMENTO + 1 BRITA), veja o total e finalize tudo de uma vez.
16. **Comprovante para imprimir**: após finalizar, mostra o comprovante com itens, preços e total, pronto para imprimir.
17. **Busca por digitação**: digite parte do nome (ex.: "cim") e escolha o produto na lista.
18. **Caixa de estoque**: ao escolher o produto, uma caixa ao lado mostra quanto ainda tem em estoque.
19. **Baixa automática**: o estoque diminui sozinho a cada venda.
20. **Proteção**: não deixa vender mais do que existe no estoque.
21. **Histórico de vendas**: mostra o que foi vendido, a quantidade, o valor e a data.
22. **Cancelar venda** (só o administrador): desfaz uma venda errada e devolve os produtos ao estoque.
23. **Tecla Enter**: agiliza o cadastro e a venda sem precisar clicar nos botões.

### 📄 Orçamentos
24. **Gerar orçamento**: monte o carrinho, digite o nome do cliente, escolha a **data de validade** (campo obrigatório) e gere o orçamento para imprimir. O estoque **não muda**.
25. **Tela de Orçamentos**: lista todos os orçamentos, com busca por cliente, telefone ou número.
26. **Idade do orçamento**: mostra "hoje", "ontem" ou "há 5 dias", e a situação em cores: 🟢 Aberto, 🟠 Vencendo (5 dias ou mais, ou faltando 2 dias para vencer), ⚫ Vencido (passou da validade), 🔵 Virou venda, 🔴 Cancelado.
27. **Transformar em venda**: coloca os itens do orçamento no carrinho, mantendo os preços combinados.

### 📊 Relatórios (só o administrador)
28. **Resumo do estoque**: total de produtos e valor total em estoque.
29. **Produtos mais vendidos**: ranking com unidades, número de vendas, valor vendido, **custo, lucro e % de lucro**.
30. **Lucro das vendas**: valor vendido, custo (preço de compra) e **LUCRO** total, em verde (ou vermelho se der prejuízo).
31. **Lucro esperado do estoque**: quanto a loja pagou pelo estoque e quanto vai lucrar se vender tudo. Avisa quais produtos ainda estão sem preço de compra.

### 🎨 Visual
32. **Cores no estoque**:
    - 🟢 **Verde**: estoque bom (10 ou mais)
    - 🟡 **Amarelo**: estoque baixo (1 a 9)
    - 🔴 **Vermelho com bolinha**: sem estoque (0)
33. **Menu laranja em destaque**, mostrando a tela atual.

## 🛠️ Tecnologias usadas

- **Python** com **Flask** (o servidor do sistema)
- **SQLAlchemy** com **SQLite** (o banco de dados)
- **HTML, CSS e JavaScript** (as telas)

## 📁 Arquivos do projeto

```
sistema-varejo-novo/
├── app.py              → programa principal (rotas e telas)
├── database.py         → banco de dados (produtos, vendas, orçamentos e usuários)
├── requirements.txt    → bibliotecas necessárias
├── chave_secreta.txt   → chave do login (criada sozinha; NÃO vai para o GitHub)
└── templates/
    ├── _menu.html      → menu de cima (igual em todas as telas)
    ├── login.html      → tela de login e de primeiro acesso
    ├── usuarios.html   → tela de usuários (só administrador)
    ├── index.html      → tela de cadastro de produtos
    ├── vendas.html     → tela de vendas e histórico
    ├── orcamentos.html → tela de orçamentos
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
4. Na primeira vez, crie o **administrador master** (nome, e-mail e senha).
5. Em **Usuários**, crie os usuários do balcão.

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
- [x] Orçamentos com validade, busca e transformar em venda
- [x] Login com e-mail e senha, administrador master e usuário de balcão
- [x] Preço de compra escondido e porcentagem de lucro
- [x] Lucro (compra × venda) nos relatórios
- [ ] Colocar o sistema online (PythonAnywhere)
- [ ] Novas melhorias sugeridas pelo usuário

## 👤 Autor

**serafim-pai**, aprendendo programação um passo de cada vez.
