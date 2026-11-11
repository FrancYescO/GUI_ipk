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

## Correzione dei preinst sul firmware (metadata policy 2)

La rivalidazione della GUI ha rilevato che `opkg status` eseguito dal `preinst`
non può acquisire il lock già detenuto dall'installazione. Il guard legge ora
`/usr/lib/opkg/status` direttamente, per tutti i provider e le capability.
Seleziona soltanto record con il nome esatto e stato finale `installed`:
il firmware conserva anche record non installati di altre versioni o
architetture. Un record non installato non può fornire l'ABI a un altro record;
più record installati dello stesso nome fanno fallire il controllo.
Restano il confronto ABI esatto, le dipendenze firmware verificate e il rifiuto
richiesto quando un vecchio generico ha ancora un modulo attivo.

La policy 2 incrementa di nuovo la revisione di tutti i 1.178 IPK kernel,
così OPKG può aggiornare gli script. I payload degli 830 moduli non cambiano;
tutti i record userspace e Release del catalogo restano identici. Il helper di
migrazione riconosce entrambe le policy 1 e 2. Non sono necessarie ricompilazioni
kernel o nuovi branch ABI per questa correzione.

Sul `.45` e sul `.204` sono state provate le installazioni con l'OPKG reale:
prima il guard rifiuta il vecchio TUN attivo, poi, con TUN inutilizzato e
scaricato, vengono installati il provider specifico e il canonico `kmod-tun`
`4.1.38-3`. Il modulo viene ricaricato; creazione e rimozione di un'interfaccia
riescono, ownership e SHA256 sono corretti, OpenVPN 2.6.23 parte per la sola
lettura della versione. VPN server/client restano disabilitate, boot ID
invariati. Non si dichiara qui una nuova prova di traffico VPN.

Una prova preliminare ha anche mostrato che `--force-reinstall` nel vecchio
OPKG rimuove il file precedente prima del `preinst`: quando il guard lo rifiuta,
il file può quindi mancare. Il file TUN del `.45` è stato ripristinato dal
backup locale verificato senza scaricare il modulo attivo o riavviare.
Le prove concluse usano l'aggiornamento normale, senza `--force-reinstall`;
il helper deve essere usato soltanto dopo il suo preflight che richiede il
modulo scaricato. `--force-overwrite` resta limitato al singolo payload già
verificato per correggerne l'ownership; non esclude i controlli ABI/dipendenze.

I log `validation/preinst-lock-{45,204}.log` sotto
`build/kernel-opkg-providers/` conservano anche i rifiuti attesi del guard.
Sei test aggiuntivi verificano assenza di chiamate OPKG annidate, ABI errata,
dipendenze stock, modulo attivo, duplicati non installati e record ambigui.
La suite locale passa 138 test (uno saltato).

## Dipendenze dei moduli stock (metadata policy 3)

La migrazione QoS di DumaOS sul `.69` ha individuato un conflitto di ownership:
installare `kmod-act-connmark` richiamava indirettamente il componente del feed
contenente `ip_tables.ko`, già posseduto dal pacchetto firmware `kmod-nf-ipt`.
Le dipendenze sceglievano il componente ricostruito anche quando lo stesso
modulo era già fornito dal firmware con ABI esatta.

La policy 3 preferisce il proprietario stock verificato per le dipendenze ELF,
per le dipendenze dei gruppi e per i componenti delle capability senza payload.
Ogni dipendenza stock mantiene la versione esatta del catalogo firmware e il
preinst verifica la sua installazione e l'ABI kernel leggendo il database OPKG,
senza acquisire nuovamente il lock. Un inventario firmware con ABI diversa dal
profilo viene rifiutato. I componenti del feed restano disponibili per le
migrazioni esplicite; la loro disponibilità non impone la sostituzione dei moduli
già presenti come dipendenze di un'applicazione.

Sul profilo 4.1.52 VBNT-K la catena di `kmod-act-connmark` richiede ora soltanto
il nuovo `act_connmark.ko` e i pacchetti stock esatti di scheduler e netfilter.
La capability `kmod-ip-tables` dipende da `kmod-nf-ipt` senza reinstallarne il
file. Non servono `--force-overwrite`, `--force-depends` o rimozioni dei moduli
firewall. La revisione dei 1.178 IPK kernel viene incrementata; gli 830 payload,
i pacchetti userspace e i componenti Release restano invariati. Il helper di
migrazione accetta anche la policy 3.

Le fixture OPKG ora includono file stock inerti e le relative liste di ownership,
oltre ai record dei pacchetti. La regressione QoS installa il pacchetto con
l'OPKG 2017 originale e controlla che hash dei file, versioni, stato e dipendenze
dei pacchetti firmware restino invariati. Non carica moduli né avvia DumaOS.
La prova con OPKG 2017 passa sulle otto ABI, inclusa l'installazione QoS sui tre
profili runtime. I risultati e il log compresso sono conservati in
`build/kernel-opkg-providers/validation/stock-owners-*`. La suite locale passa
155 test (tre saltati per i requisiti dell'ambiente).

## Standard-path firmware feeds (metadata policy 4)

The five additional 4.1.52 profiles now publish modules in `/lib/modules/4.1.52/`,
including cryptodev. Cryptodev on the three original profiles also uses the
standard module directory. The source bundles remain immutable and the 830
ELF payloads retain their hashes; the publication repacks paths and metadata.
Physical packages replace the `-candidate` suffix with `-manual`. Source IPKs
are archived for provenance and are excluded from active indexes. Previous
4.1.52 candidate URLs serve aliases of the canonical feeds.

Firmware OPKG ownership inventories for all five profiles are pinned to
original-image repository commits, with per-control/list SHA256 hashes. Exact
stock dependency owners are preferred over rebuilt components. The active
catalog contains 1,449 kernel records, including 619 complete capabilities.
All eight profiles provide TUN through a real module or verified builtin.
Pre-install guards accept vendor whitespace variants in exact kernel bindings
and still reject missing, wrong or ambiguous installed ABI records.

Runtime evidence is bound to module SHA256 and ABI. Only VCNT-3 CDC Ethernet
and RNDIS host gained runtime labels for USB binding/DHCP. Other new modules
remain labelled offline-checked. No package hook loads or unloads drivers, adds
autoload entries, forces replacement or bypasses dependencies. Existing stock
ownership needs the controlled migration helper after quiescing the module;
old installed staging packages are removed separately after migration. The
legacy 4.1.38 candidate feeds retain their staging behavior.

Validation passes 158 local tests (three environment-dependent skips). The
unpatched OPKG 2017 passes installation/migration scenarios on eight ABIs,
including five explicit CDC/RNDIS standard-path migrations retaining stock
USBnet. Evidence is in `validation/standard-paths-*` beside this document's
source metadata. Rendered manifests expose eight selectable profiles and only
two legacy staging profiles. No new hardware run or reboot is claimed.

## 4.1.38 consolidation (metadata policy 5)

The 4.1.38 feeds now use standard `/lib/modules/4.1.38/` paths for all active
packages. All candidate URLs are aliases; no staging-only feed remains.
Duplicate consolidation retains 223 unique modules on VBNT-O and 214 on
VBNT-K/S. Ninety-five archived duplicates are omitted, always preferring the
already published standard-path payload, including all exact hardware-tested
reference payloads. Source archives remain available for historical audits.

The active catalog has 735 unique module payloads and 974 complete capability
packages (1,709 kernel records). ELF bytes are unchanged. Legacy import closure
is checked against pinned kernel exports and the retained module exports.
SPU is the explicit exception: the saved kernel-only list lacks vendor
RDPA/BDMF exports, while the identical retained SPU payload already has
hardware validation. `validation/legacy-4138-selection.json` records input
hashes, discarded/retained hashes and the exact exception. Runtime labels
are tied to existing per-payload evidence; all other modules retain offline
labels. Public pages identify model and firmware without private IP suffixes.
