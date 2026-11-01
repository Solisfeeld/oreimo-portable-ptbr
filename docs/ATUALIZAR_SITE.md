# Como atualizar o site

O site fica em `site/`. Cada alteração nessa pasta em `main` é enviada à branch `gh-pages` pelo fluxo `.github/workflows/publicar-site.yml`.

Na árvore completa do projeto, as fontes públicas ficam em `ferramentas/publicacao/docs_publicos/`. Atualize essa fonte e execute `python3 ferramentas/publicacao/preparar.py <pasta_do_repositorio_publico>` para regenerar o repositório público antes de publicar. A pasta de destino deve ficar fora da árvore completa do projeto.

## Mudar o estado de um disco

Em `site/index.html`:

1. Nos selos da abertura, troque a classe do disco: `selo-off` (indisponível), `selo-prep` (em andamento) ou `selo-ok` (concluído).
2. Na seção `id="downloads"`, atualize o título do cartão do disco. Use só dados reais.
3. Repita no `README.md`.

## Publicar um download

O Disco 1 já tem uma ISO hospedada externamente; não há patch independente. O estado técnico está em [PATCH.md](PATCH.md).

Para atualizar um download:

1. Confirme que o arquivo está acessível publicamente e que nome, tamanho e metadados correspondem ao arquivo aprovado.
2. Mantenha o botão da seção `id="downloads"` como link HTML normais para a URL direta do arquivo. Não dependa de `download` entre domínios nem de JavaScript para iniciar o download.
3. Atualize os selos, a seção `id="instalacao"`, as perguntas frequentes e o `README.md` com o mesmo endereço e estado.
4. Verifique o layout em computador e celular e acompanhe o workflow e o site público depois do push.

Endereço atual do Disco 1: `https://archive.org/download/oreimo-portable-ga-tsuzuku-ptbr/Oreimo_Disco1_PTBR.iso`.

O Disco 2 permanece indisponível, sem botão de download e sem previsão de lançamento.

## Regras

* Nada de download para arquivo que não existe.
* Capturas só da versão aprovada, sempre identificadas como capturas.
