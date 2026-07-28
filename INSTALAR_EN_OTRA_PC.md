# Instalar la app en otra PC

Guia para dejar el bot funcionando en una segunda computadora (por ejemplo: esta
PC opera Tradier y la otra opera Alpaca).

**Se hace UNA sola vez.** Despues, para traer las correcciones, alcanza con hacer
doble click en `Actualizar.bat`.

---

## Antes de empezar

Necesitas:
- La direccion del repositorio en GitHub (te la paso el asistente).
- Tus claves (el archivo `credentials.ini` de la PC principal), **en un pendrive**.
  Nunca las mandes por mail, WhatsApp ni las subas a una carpeta compartida.

---

## Paso 1 — Instalar Python

1. Entra a **python.org/downloads** y baja la ultima version para Windows.
2. Al instalar, **TILDA la casilla "Add Python to PATH"** (abajo de todo, en la
   primera pantalla). Es el paso que mas se olvida y sin eso no funciona nada.
3. Siguiente / siguiente / finalizar.

## Paso 2 — Instalar Git

1. Entra a **git-scm.com/download/win** y baja el instalador.
2. Siguiente / siguiente / finalizar (todas las opciones por defecto estan bien).

## Paso 3 — Bajar la app

1. Elegi donde va a vivir la app (por ejemplo, el Escritorio o `C:\`).
2. Abri esa carpeta, hace **click derecho** en un espacio vacio y elegi
   **"Abrir en Terminal"** (o "Git Bash Here").
3. Pega este comando (es la direccion de TU repositorio):

```bash
git clone https://github.com/javipere-git/bot.git
```

4. La primera vez te va a pedir iniciar sesion en GitHub: usa tu usuario y
   contraseña de GitHub (se abre una ventana del navegador).

Eso crea la carpeta `bot` con toda la app adentro.

## Paso 4 — Instalar las librerias

Dentro de la carpeta `bot`, hace doble click en **`Actualizar.bat`**.
Se encarga solo de instalar todo lo que hace falta.

## Paso 5 — Poner tus claves

1. Abri la carpeta `config` de la app.
2. Copia ahi tu archivo **`credentials.ini`** desde el pendrive.
   - Si preferis escribirlo a mano: copia `credentials.example.ini`, renombralo a
     `credentials.ini` y completa las claves.
3. **Recomendacion de seguridad**: si esta PC solo va a operar Alpaca, deja SOLO
   las claves de Alpaca y borra las de Tradier. Menos claves dando vueltas,
   menos riesgo. (Excepcion: el perfil "Alpaca con datos de Tradier" necesita el
   token de produccion de Tradier tambien.)

## Paso 6 — Configurar la carpeta de registros (para soporte a distancia)

Para que los problemas de ESTA PC se puedan revisar desde la PC principal:

1. Instala **Google Drive para escritorio** (google.com/drive/download) e inicia
   sesion. OJO: NO alcanza con usar Drive desde el navegador; hace falta el
   programa, que es el que crea una carpeta de verdad en la PC (aparece como una
   unidad nueva, normalmente `G:`, con "Mi unidad" adentro).
2. Crea (o ubica) ahi la carpeta de los registros, por ejemplo `Mi unidad\bot-logs`.
3. Para saber la ruta exacta: click derecho sobre la carpeta -> "Copiar como ruta
   de acceso".
4. Abri `config\credentials.ini` con el Bloc de notas y completa la ultima linea:

```
[logs]
carpeta = C:\Users\TU-USUARIO\Mi unidad\bot-logs
```

Los registros se llaman `registro_<NOMBRE-DE-ESTA-PC>_<perfil>.log`, asi que los
de las dos maquinas conviven sin pisarse.

## Paso 7 — Abrir la app

Hace doble click en **`lanzar_app.pyw`**.

Para tenerlo mas a mano: click derecho sobre ese archivo -> "Mostrar mas
opciones" -> "Enviar a" -> "Escritorio (crear acceso directo)".

---

## El dia a dia

| Situacion | Que haces |
|---|---|
| El asistente corrigio algo | Cerras la app y haces doble click en `Actualizar.bat` |
| Algo falla en esta PC | Le avisas al asistente: el lee el registro desde Google Drive |
| Queres saber que version tenes | Se anota en el registro cada vez que abris la app |

**Importante:** las dos PCs no tienen que quedar con versiones distintas. Cuando
se corrige algo, conviene actualizar las dos.

---

## Preguntas frecuentes

**¿Puedo operar las dos PCs al mismo tiempo?**
Si. Son cuentas y conexiones distintas, no se pisan. Lo unico compartido es el
cupo de llamadas del broker (ver MANUAL.md).

**¿Y si quiero que la PC 2 pase a ser la principal?**
Se puede, sin problema: la copia maestra vive en GitHub y las maquinas son
intercambiables. Avisale al asistente y te guia.

**¿Mis claves se suben a GitHub?**
No. `credentials.ini` esta excluido a proposito y nunca viaja. Por eso hay que
copiarlo a mano una sola vez.
