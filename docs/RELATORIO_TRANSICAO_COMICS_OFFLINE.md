# Estado Atual - Organizacao de Comics por Nome de Arquivo

Este documento descreve o comportamento vigente da organizacao de comics no sistema.

## Visao Geral

A organizacao de comics utiliza metadados locais extraidos do nome do arquivo e da estrutura de pasta.
O fluxo de processamento aplica validacao de esquema antes de criar destino e registrar no banco.

Padrao canonico de nome aceito para destino:

`Titulo (Ano) - Serie (opcional) #Edicao.ext`

Exemplos:
- `Invencivel (2003) #001.cbz`
- `Invencivel (2003) - Biblioteca Galactica #010.cbr`

## Regras de Esquema

Campos obrigatorios para organizacao:
- `title`
- `year`
- `issue_number`

Campos opcionais:
- `series`
- `publisher`
- `author`
- `description`
- `story_arc`
- `chapter_title`

Quando os campos obrigatorios nao estao presentes no nome:
- o arquivo e marcado como `skipped`
- o motivo e salvo no banco de nao organizados
- a operacao pode ser revisada pelo fluxo de sugestoes de nome

## Fluxo Operacional

1. Detectar tipo de midia.
2. Extrair metadados de comics pelo parser compartilhado.
3. Validar esquema.
4. Resolver conflito de destino conforme estrategia configurada.
5. Organizar (hardlink/copia conforme estrategia/ambiente).
6. Registrar no banco de organizados.
7. Remover entrada correspondente do banco de nao organizados quando houver sucesso.

## Banco de Nao Organizados

Entradas de comics nao organizados incluem:
- caminho do arquivo
- tipo de midia
- motivo de skip
- contador de tentativas
- timestamp da ultima tentativa

Esse registro permite reprocessamento seguro e rastreavel em ciclos futuros.

## Sugestoes de Nome

O modulo de sugestoes usa a mesma base de parsing e validacao do organizador.
Assim, sugestoes com alta confianca ja seguem o esquema aceito pelo fluxo de organizacao.

## Checklist de Conformidade

- [x] Parser e organizador de comics usando regra de nome compartilhada.
- [x] Validacao de esquema antes da organizacao.
- [x] Registro de skips no banco de nao organizados.
- [x] Remocao de nao organizados apos organizacao bem-sucedida.
- [x] Sugestoes de nome alinhadas com as mesmas regras do organizador.
