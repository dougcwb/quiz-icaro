# 🎮 Mundo de Estudos - Quiz Retrô

Um jogo interativo de perguntas e respostas criado para transformar a revisão escolar do 4º ano em uma experiência divertida e engajadora, inspirada em videogames clássicos de 16 bits.

O sistema sorteia perguntas de diferentes disciplinas (Matemática, História, Geografia, Ciências, Português e Inglês) e incentiva a repetição e o aprendizado através de um sistema de pontuação e recordes.

## ✨ Funcionalidades

* **Sistema de Combos e Pontuação:** Acertar de primeira garante mais pontos e aumenta o multiplicador de combo. Errar dá uma segunda chance com dicas, mas zera o combo.
* **Progresso e Maestria:** O jogo rastreia o progresso do jogador (ex: 12/15) indicando quantas perguntas únicas daquela matéria ele já dominou acertando de primeira.
* **Recordes Globais (High Score):** As maiores pontuações de cada disciplina ficam salvas na nuvem para incentivar a superação.
* **Suporte a Gamepads:** Pode ser jogado no teclado ou usando controles físicos (como os de Xbox ou consoles portáteis retrô), com navegação completa pelos menus.
* **Interface Imersiva:** Design pixel art com efeitos sonoros, animações de vitória (confetes) e penalidades ao errar.

## 🕹️ Como Jogar

O jogo é super intuitivo e foca na agilidade. 

**No Teclado:**
* **Navegar no Menu:** Setas direcionais (`↑` `↓` `←` `→`).
* **Entrar no Quiz:** `Enter`.
* **Responder:** Teclas `1`, `2`, `3` e `4` (representando as alternativas A, B, X e Y).
* **Voltar/Sair:** `Esc` ou tecla `2` na tela de fim de jogo.

**No Controle (Gamepad):**
* **Navegar no Menu:** D-Pad (direcionais em cruz) ou Botões de Ombro (L1/R1).
* **Entrar no Quiz:** Botão `A`.
* **Responder:** Botões `A`, `B`, `X`, `Y` correspondem às alternativas na tela.

## 🛠️ Tecnologias e Serviços Utilizados

Este projeto foi construído para ser leve, rápido e fácil de atualizar:

* **Frontend:** HTML5, CSS3 e Vanilla JavaScript. Estilização baseada em fontes retrô (Google Fonts) e responsiva.
* **Backend:** Python com Flask, servindo a API de perguntas e gerenciando as rotas.
* **Banco de Dados:** PostgreSQL hospedado no **Supabase**. Guarda os recordes e o progresso das perguntas de forma permanente na nuvem.
* **Hospedagem:** O sistema roda na nuvem através do **Render** (Web Service), permitindo acesso de qualquer lugar via link público.
* **Versionamento:** Integrado com o **GitHub**. Para adicionar novos conteúdos, basta subir um arquivo `.json` com as perguntas na pasta `quizzes` e o servidor atualiza automaticamente.