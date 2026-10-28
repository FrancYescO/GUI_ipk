# Dipendenze OPKG dei moduli kernel

I feed distinguono tre casi: moduli realmente installabili, funzionalità già
integrate nel kernel originale e moduli candidate depositati soltanto in staging.
Solo i primi due possono soddisfare le dipendenze standard delle applicazioni.
La dipendenza dal pacchetto `kernel` contiene sempre l'intera versione ABI.

## Copertura di tutti i moduli

La pubblicazione normalizza tutti gli 830 IPK kernel, senza ricompilare né cambiare
un byte dei `.ko`. I nomi standard che corrispondono a un modulo completo sono
esposti con `Provides`. Un pacchetto composto, per esempio `kmod-sched-core`, viene
fornito solo se tutti i componenti previsti per quel firmware sono disponibili.
I gruppi completi usano pacchetti di capability con dipendenze esatte sui singoli
componenti; una parte di un gruppo non viene presentata come il gruppo intero.

Le dipendenze già fornite dal firmware rimangono tali: il pacchetto componente
richiede la loro versione e la preinstallazione verifica anche il loro vincolo
ABI, non soltanto il nome. Le registrazioni senza un vincolo kernel esatto non
sono accettate come prova di compatibilità. Le funzionalità builtin sono derivate
dalla configurazione originale e da regole Makefile/Kconfig non ambigue.

Per TUN sono disponibili provider operativi sui tre profili runtime e sui due
firmware VCNT-A/VBNT-V che lo hanno integrato nel kernel. Nei profili modulari
VCNT-2/3/J il TUN ricompilato resta un candidate: installare un file in staging
non dimostra che la funzionalità sia attiva e non soddisfa `kmod-tun`.
Questo non impedisce al pacchetto TUN originale del firmware di soddisfare la
dipendenza quando è già installato con la corretta ABI.

I nuovi IPK includono esplicitamente tutte le directory padre, necessarie
all'estrazione con l'OPKG del firmware. Non introducono avvio automatico,
caricamento di moduli, rimozione di moduli attivi o bypass delle dipendenze.
Le revisioni dei pacchetti sono incrementate. Le vecchie copie sorgente rimangono
raggiungibili per i rapporti storici e la verifica dei checksum, ma non figurano
negli indici attivi: per installare usare sempre gli indici correnti.

## Perché non viene usato Replaces

L'OPKG del firmware 18.x è alla revisione
`4bd8601ebd95c130e504cc724b0c5eb163050982` del 28 luglio 2017.
In `parse_replacelist()` il ciclo incrementa `count` due volte, lasciando una
posizione non inizializzata e scrivendo il terminatore fuori dall'array.
La prova ridotta sul modem ha riprodotto il crash anche con un singolo `Replaces`.

I pacchetti e gli indici normalizzati quindi omettono quel campo, compresi i
vecchi riferimenti ai nomi manuali. Le dipendenze sono risolte con `Provides`
e, dove serve, un pacchetto standard che dipende dal componente con ABI esatta.
Non è necessario cambiare il package manager del modem.

Sorgente del difetto:
https://github.com/openwrt/opkg-lede/blob/4bd8601ebd95c130e504cc724b0c5eb163050982/libopkg/pkg_depends.c

## Installazione pulita e migrazione

Con il solo feed corrispondente all'ABI installata, una nuova installazione di
OpenVPN può risolvere `kmod-tun` senza ricorrere al vecchio generico.
Il setup della GUI deve aver rimosso il vecchio feed kernel Ansuel e i suoi indici
in cache; questo repository non può eliminare gli URL di un altro repository.
Le correzioni degli script GUI sono documentate nella chat di validazione DumaOS.

Se un generico è già installato, il cambio di ownership dei file deve essere
controllato. Lo script `scripts/migrate-kernel-package.sh` lavora su un singolo
IPK ABI-specifico e rifiuta file aggiuntivi, checksum errato, ABI diversa,
moduli in staging o un modulo attualmente caricato. Occorre prima fermare i
consumatori e predisporre una finestra di manutenzione; lo script non scarica
né forza la rimozione di alcun modulo kernel.

Esempio per il profilo VBNT-K/S 4.1.38, dopo avere copiato lo script sul modem:

```sh
opkg update
sh /tmp/migrate-kernel-package.sh kmod-tun-vbnts-4.1.38-manual
# Dopo la verifica del piano e con TUN non caricato:
sh /tmp/migrate-kernel-package.sh --apply kmod-tun-vbnts-4.1.38-manual
```

La fase applicativa usa `--force-overwrite` solo dopo aver verificato che l'IPK
contenga esattamente il singolo `.ko` previsto, nell'unico percorso atteso.
Non usa `--force-depends`, `--nodeps` o caricamento forzato del kernel.
Il provider ABI-specifico prende la proprietà del file; gli eventuali wrapper
standard disponibili vengono poi aggiornati normalmente. Le applicazioni
restano installate. Il file e il suo hash vengono ricontrollati alla fine.
L'operazione non attiva il driver.

Non viene rimossa alla cieca la registrazione di un vecchio pacchetto: l'OPKG
2017 può rifiutare la rimozione anche quando un provider alternativo è presente.
Dove non è pubblicato un wrapper standard sostitutivo, la registrazione stock
può rimanere, mentre il modulo aggiornato e le sue dipendenze ABI-specifiche
sono espliciti. Una dipendenza firmware non verificabile richiede il ripristino
originale, non l'installazione di un altro generico.

## Riproducibilità e prove

`build/kernel-opkg-providers/legacy-map.json` conserva composizione dei pacchetti,
riferimenti immutabili, hash degli IPK usati solo come metadata e regole sorgente.
Nessun vecchio binario generico è riutilizzato. `firmware-packages.json` contiene
soltanto metadata e liste di file dei pacchetti con ABI esatta osservati sui tre
modem. `source-records.json.gz` fissa i riferimenti del catalogo precedente.

La suite verifica l'identità di tutti gli 830 payload, la riproduzione degli IPK
pubblicati, la chiusura dei gruppi, l'assenza di `Replaces`, le directory e le
separazioni fra profili. La CI ricompila l'OPKG 2017 originale, non corretto,
con libubox fissata e prova tutti gli otto profili in `--offline-root`.
Le fixture non caricano moduli né eseguono applicazioni: i vecchi moduli sono
sostituiti da dati di prova non eseguibili. Verificano installazione pulita,
provider builtin, migrazione di proprietà, gruppi multipli, conservazione dei
consumatori e rifiuto dell'ABI sbagliata. I candidate modulari non devono
soddisfare accidentalmente la dipendenza TUN.
