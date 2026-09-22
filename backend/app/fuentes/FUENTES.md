# Tipografías empaquetadas

Todas se usan desde `@font-face` en las plantillas (`app/plantillas`) y se copian a la imagen de Docker.

| Archivo | Familia | Para qué | Licencia |
|---|---|---|---|
| `IBMPlexSans-*.ttf` | IBM Plex Sans | PDF base de la propuesta | SIL Open Font License 1.1 (`LICENSE.txt`) |
| `PublicSans-*.ttf` | Public Sans | Presentación editorial: sustituto de Everett | SIL Open Font License 1.1 (`PublicSans-OFL.txt`) |
| `BebasNeue-Regular.ttf` | Bebas Neue | Presentación editorial: opción de títulos | SIL Open Font License 1.1 ([Bebas Neue](https://github.com/dharmatype/Bebas-Neue)) |

## Everett (tipografía de marca, no incluida)

Everett tiene licencia comercial y no viene con los archivos de marca, así que no está en el repo.
El render la usa automáticamente si se colocan los archivos en `app/fuentes/marca/`:

```
app/fuentes/marca/Everett-Regular.otf     (o .ttf / .woff2)
app/fuentes/marca/Everett-Light.otf       (opcional)
app/fuentes/marca/Everett-Medium.otf      (opcional)
```

Sin esos archivos, la presentación sale con Public Sans, que es la que usa la presentación de ejemplo
de la marca. Antes de subirlos al repo hay que revisar que la licencia contratada permita usarlos en un
servidor.
