# 🎮 Mundo de Estudos - Quiz Retrô

Um jogo interativo de perguntas e respostas criado para transformar a revisão escolar em uma experiência imersiva e divertida, inspirada em videogames clássicos de fliperama e consoles de 16 bits.

## 🛠️ Tecnologias Utilizadas
* **Backend:** Python com Flask.
* **Banco de Dados:** PostgreSQL hospedado no Supabase (com *Connection Pooling* IPv4).
* **Frontend:** HTML5, CSS3, JavaScript puro (Gamepad API).
* **Hospedagem:** Render.

## ✨ Funcionalidades Principais

* **Identificação de Jogadores:** Sistema de sessões que permite a cada criança ter seu próprio progresso, recordes de estrelas e questões dominadas sem sobrescrever o colega.
* **Estatísticas Globais:** Contador de visitas diárias e totais exibido no menu principal.
* **Gamificação e UI:** Sistema de Combos por acertos consecutivos, "Vitória Royale" ao concluir o quiz, e dicas automáticas de erro para forçar a aprendizagem.
* **Suporte Dinâmico a Controles:** Mapeamento inteligente na tela de login. O jogador escolhe o controle (Xbox, PlayStation, Switch ou Teclado) e o jogo adapta toda a interface visual (A/B/X/Y, ✖/⭕/🟦/🔺) e a lógica de botões internamente (incluindo a inversão física dos botões A/B do Nintendo Switch).

## 🤫 Códigos Secretos (Easter Eggs)

Para manter a interface limpa e trazer o clima de videogame antigo, as funções administrativas estão escondidas por sequências de botões na tela de seleção de disciplinas:

1. **🏆 Hall da Fama (Leaderboard):** 
   * **Código:** `Y, X, B, A` (Xbox) | `🔺, 🟦, ⭕, ✖` (PS) | `4, 3, 2, 1` (Teclado).
   * Mostra o ranking global de todos os jogadores pelas estrelas acumuladas.
2. **⚠️ Zerar Progresso (Reset Específico):** 
   * **Código:** `A, B, X, Y` (Xbox) | `✖, ⭕, 🟦, 🔺` (PS) | `1, 2, 3, 4` (Teclado).
   * Pressione essa sequência *com a matéria que deseja apagar selecionada*. Ele exclui apenas o recorde daquele teste para o jogador logado.

## 🕹️ Como Jogar

**Navegação Geral:**
* **Selecionar Controles no Login:** Botões `L` / `R` (Ombro) ou Direcionais para os lados.
* **Navegar nas Matérias:** Direcional D-Pad ou Setas do Teclado (Cima/Baixo).

**Botões de Ação (Dependem da Escolha Inicial):**
* **Teclado:** `Enter` (Confirmar), `Esc` (Cancelar/Voltar), `1 a 4` (Alternativas).
* **Xbox / R36S:** `A` (Confirmar), `B` (Cancelar/Voltar).
* **PlayStation:** `✖` (Confirmar), `⭕` (Cancelar/Voltar).
* **Nintendo Switch:** `A` [Botão Direito] (Confirmar), `B` [Botão Inferior] (Cancelar/Voltar).

## 🔒 Variáveis de Ambiente e Segurança
O repositório está configurado para ocultar credenciais. Para rodar o projeto localmente, é necessário criar um arquivo `.env` na raiz contendo:
`DATABASE_URL=postgresql://usuario:senha@host:6543/postgres`
