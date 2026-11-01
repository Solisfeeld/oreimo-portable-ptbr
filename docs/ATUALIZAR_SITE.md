# Como atualizar o site

O site fica em `site/`. Cada alteração nessa pasta em `main` é enviada à branch `gh-pages` pelo fluxo `.github/workflows/publicar-site.yml`.

## Mudar o estado de um disco

Em `site/index.html`:

1. Na seção `id="progresso"`, procure `data-disco="2"`.
2. Troque o selo: `selo-off` (indisponível), `selo-prep` (em andamento) ou `selo-ok` (concluído).
3. Atualize o texto ao lado. Use só dados reais.
4. Repita na seção `id="downloads"`, no cartão do disco, e nos selos da abertura.

## Publicar um patch

Só depois de resolver [PATCH.md](PATCH.md) e publicar a Release com o arquivo:

1. Na seção `id="downloads"`, troque `<p class="estado-botao">` por um link `<a class="botao botao-principal">` para o arquivo da Release.
2. Troque o aviso `aviso-principal`, os selos da abertura e a seção `id="instalacao"`.
3. Atualize as perguntas frequentes e o `README.md`.

## Regras

* Nada de download para arquivo que não existe.
* Sem capturas nem artes oficiais sem avaliar os direitos.
* Imagem ilustrativa sempre identificada como ilustração.
