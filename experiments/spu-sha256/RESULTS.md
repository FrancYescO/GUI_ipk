# SPU: stato attuale e riepilogo completo dei test

Aggiornato al **21 ottobre 2026**. Modem **Technicolor DGA4130 / VBNT-K**,
SoC **BCM63138**, firmware **19.4.1051**, kernel in esecuzione **Linux 4.1.52**.
I nomi storici `vbntj`, `damson` e `VBNTJ_502L07p1` presenti nei percorsi,
artefatti e metadati di compilazione non identificano il modello del modem.
Questo documento riunisce le prove del 20–21 ottobre e l'ultimo stato verificato;
il suo aggiornamento non costituisce una nuova sessione di test.

## Stato attuale

| Area | Stato verificato | Limite aperto |
| --- | --- | --- |
| SPU per kernel 4.1.52 | Build Actions, IPK effettivo estratto e testato da `/tmp`, pubblicato nel feed | Drop Runner sotto carico; nessuna certificazione WAN o di lunga durata |
| SPU per kernel 4.1.38 | Compilato e pubblicato nel feed dedicato | Non eseguito sul modem con kernel 4.1.52 |
| AES128/192/256 con SHA1-96 | Percorso hardware Runner funzionante | Perdite TCP/UDP ancora osservabili |
| AES128/192/256 con SHA256-128 | Funzionante con fallback software | Accelerazione completa SHA256-128 non ottenuta |
| AES/SHA256 ARM scalari, AES-GCM e WireGuard | Correttezza e traffico verificati | Misure locali; percorso esterno Docker/NAT limitante |
| Ibrido Runner/SHA256 software, con o senza copie | Vettori e alcune prove brevi superati | Stalli, richieste kernel pendenti, riavvii: solo laboratorio |
| Drain RX + fallback per pool pieno | Riprodotto blocco seguito da riavvio anche con copie | Causa precisa non catturata; combinazione bloccata negli script |
| Windows/DHCP e tabella RDPA piena | BLOG disabilitato per default; avviso tabella piena osservato | Scenario con client reali e saturazione tabella non dichiarati risolti |

I feed stabili mantengono SHA256-128 software e non includono l'ibrido o le
patch sperimentali delle code. Nessun esperimento installato con OPKG o
configurato per autoload; moduli caricati soltanto da `/tmp`. Nessuna scrittura
a firmware Runner o registri sconosciuti, nessun unload forzato.

## Metodo e limiti delle misure

Le coppie indicano **Mbit/s ricevuti, direzione diretta / inversa**. Salvo la
sezione sul peer esterno, entrambi gli endpoint sono namespace sullo stesso
modem: condividono CPU e risorse. Non sono velocità WAN. Chiavi sintetiche,
namespace riservate e pulizia circoscritta alle prove. RPS/offload modificati
solo sulle veth; affinità IRQ e offload delle interfacce fisiche non modificati.

Il vecchio iperf3 3.1.4 del firmware emette avvisi `tcpspdtest_protocol` anche
senza `-H` e ha riportato perdite UDP fino all'1,10% anche senza VPN. I risultati
iniziali sono quindi separati da quelli con upstream 3.18. Le perdite del vecchio
strumento non sono tutte attribuibili alla crittografia; gli esaurimenti contati
dal driver sono evidenze indipendenti. Piccole differenze fra prove brevi non
stabiliscono un ordinamento affidabile delle prestazioni.

## Pacchetto stabile: correttezza, matrice e ciclo di vita

Verificati checksum, ELF ARM, vermagic esatto, simboli e canary ABI. OPKG
`--noaction` accetta `arm_cortex-a9`; il modulo estratto dall'IPK realmente
scaricato da Actions coincide con quello grezzo. Nessuna installazione persistente.

Le patch stabili instradano le dimensioni di tag non supportate sul provider
software sincrono, disattivano BLOG ESP flow offload per default e rendono
idempotente la distruzione dell'oggetto RDPA IPsec. Disabilitare BLOG evita
il percorso implicato dal forum, ma non prova risolti i crash Windows/DHCP.

| Prova | Esito |
| --- | --- |
| Decrittazione AES128/SHA256-128 e rifiuto tag alterato | Superate, software |
| Decrittazione AES128/SHA1-96 e rifiuto tag alterato | Superate, hardware |
| Due tunnel ESP iniziali, ping bidirezionale | Tutte le 20 risposte ricevute |
| Dieci cicli load/start/KAT/stop/unload | Tutti i 40 controlli superati |
| Matrice AES128/192/256 × SHA1/SHA256 | Tutti i 36 ping frammentati da 4.000 byte e i 12 trasferimenti TCP completati |
| Cambio chiavi sulle SA attive | Tutti i 72 ping frammentati prima/dopo il cambio completati |
| Sei UDP da 3 s a 10 Mbit/s dopo rekey | SHA256: zero perdita riportata; SHA1: 3,1%, 0%, 5,4% per AES128/192/256 |
| Stop/unload | Completati dopo attesa del teardown asincrono delle namespace |

Matrice iniziale con iperf3 3.1.4, trasferimenti di circa 3–5 s:

| Percorso | AES128 | AES192 | AES256 |
| --- | ---: | ---: | ---: |
| SHA1-96 hardware | 84,7 / 81,8 | 83,3 / 82,1 | 70,3 / 82,9 |
| SHA256-128 software | 37,0 / 35,5 | 33,7 / 33,6 | 31,7 / 33,6 |

Il controllo breve sull'IPK finale ha dato 86,3 Mbit/s SHA1 e 37,6 SHA256.
Nella matrice hardware: 105 drop in cifratura e 366 in decifratura; i casi
software non li aumentavano. Autenticazione/replay XFRM senza errori; i tag
errati deliberati sono contabilizzati separatamente. Drop hardware non eliminati.
La tabella condivisa RDPA `ipv4_host_address_table` segnala ancora esaurimento
aggiungendo gli indirizzi sintetici: non è stata espansa né dichiarata corretta.

## SHA256 hardware, provider ARM e ibrido: vettori e guardie

| Esperimento | Risultato |
| --- | --- |
| Bypass della sola barriera sulla dimensione tag | Pacchetto valido indipendente rifiutato con `-EBADMSG (-74)`: ingress hardware 1, fallback 0, errore autenticazione 1 |
| SHA256-96 Runner con AES128/192/256 | Cifratura, decifratura e rifiuto tag alterato superati |
| AES ARM e SHA256 ARM scalari | Confronto con riferimento generico e rifiuto tag alterato superati; niente NEON/VFP |
| Ibrido con framing privato SHA1 o SHA256-96 | 48 controlli per variante su cifratura, decifratura, tag, ESP, IV e ciphertext superati |
| Metadati AEAD iniziali, massimo digest 16 byte | Creazione SA fallita; corretti a 32 byte, tag operativo solo 16 byte |
| Prima modalità senza copie | 96 controlli a offset ESP 0/20, 36 operazioni senza copie per offset, superati |
| Copie con guardie rafforzate | Altri 96 controlli a offset 0/20 su header IPv4, lunghezza e coda, superati |
| Pool 256, tag completo incluso ultimo byte | 60 controlli senza copie per offset 0/20, 45 operazioni senza copie per offset; altri 60 con copie a offset 20, superati |
| Prima diagnostica RX/fallback | 60 controlli per percorso hardware e software forzato, superati con zero pendenti |
| Bundle con nuove guardie RX, 21 ottobre | AES128/192/256 a offset 20, inclusi tag corrotti: hardware 45 completamenti/0 fallback; software forzato 45 fallback/0 RX hardware; zero pendenti e unload normale |

L'ibrido verifica sempre il tag SHA256-128 completo in software prima della
decifratura hardware. Il framing privato a 96 bit non modifica il protocollo
esterno e non è accelerazione completa SHA256-128. La variante SHA1 usa SHA1
solo internamente. Le guardie non dimostrano sicurezza sotto carico: gli stalli
successivi restano validi. Build normali: `in_place=1` rifiutato; build dedicata:
attivazione esplicita, skb lineare/esclusivo e layout esatto, altrimenti copie.

La ricognizione del sorgente non trova una lunghezza ICV in
`rdpa_ipsec_sa_desc_setting`; le istruzioni Runner sono array binari, senza
assembler della routine IPsec. `impl4` riguarda altri chip e non sostituisce
direttamente `impl3` sul BCM63138. Nessun firmware alternativo tentato.

## Matrice TCP iniziale: iperf3 3.1.4

SHA256-128 esterno in ogni riga, 5 s per direzione, replay-window 32 e ping
frammentati prima di ogni caso. Contatori XFRM senza errori nei casi completati.
Le righe ibride sono risultati storici di laboratorio, non raccomandazioni.

| Configurazione | AES128-CBC | AES192-CBC | AES256-CBC |
| --- | ---: | ---: | ---: |
| Fallback SPU pubblicato | 35,40 / 36,68 | 34,62 / 35,65 | 33,55 / 31,46 |
| Software generico senza SPU | 35,97 / 37,75 | 34,60 / 35,65 | 32,72 / 33,55 |
| Solo SHA256 ARM | 38,70 / 40,08 | 36,38 / 35,65 | 34,41 / 36,06 |
| Solo AES ARM | 41,82 / 40,06 | 39,04 / 38,77 | 36,57 / 35,82 |
| AES + SHA256 ARM | 42,91 / 43,71 | 38,97 / 42,22 | 39,36 / 39,18 |
| Fallback SPU + AES/SHA256 ARM | 42,19 / 42,21 | 44,79 / 42,16 | 37,10 / 38,95 |
| Ibrido AES Runner / framing SHA1 / SHA256 C | 34,96 / 37,77 | 32,21 / 37,60 | 37,70 / 37,97 |
| Ibrido AES Runner / framing SHA1 / SHA256 ARM | 40,45 / 39,36 | 40,52 / 40,22 | 39,03 / 40,73 |
| Ibrido AES Runner / framing SHA256 / SHA256 C | 40,71 / 42,34 | 40,31 / 42,57 | 41,51 / 42,35 |
| Ibrido AES Runner / framing SHA256 / SHA256 ARM | 41,84 / 44,69 | 46,02 / 44,18 | 44,12 / 45,88 |
| Ibrido senza copie / SHA256 C | 44,14 / 45,69 | 40,92 / 45,57 | 45,66 / 45,81 |
| Ibrido senza copie / SHA256 ARM | 49,30 / 48,72 | 49,09 / 49,53 | 41,45 / 50,20 |

Ripetizione senza copie/ARM da 10 s: AES128 48,56/48,94, AES192 48,02/48,80,
AES256 48,66/49,45. Ripetizione con copie AES256: 45,86/45,61. Non provano
stabilità: le sequenze successive si bloccano. Il primo ibrido SHA256/ARM conta
298 drop in cifratura e 420 in decifratura, senza errori del tag esterno.

## Matrice con iperf3 upstream 3.18

Stesso strumento su entrambi gli endpoint, RPS 3 sulle veth, IPsec 5 s per
direzione, WireGuard 10 s. Ping frammentati e pulizia completati, zero errori
autenticazione/replay IPsec. Nessun modulo SPU in queste righe.

| Configurazione | AES128 | AES192 | AES256 |
| --- | ---: | ---: | ---: |
| AES-CBC / SHA256-128 generici | 43,33 / 42,77 | 38,04 / 43,83 | 38,34 / 33,34 |
| AES-CBC / SHA256-128 ARM | 48,83 / 48,85 | 42,73 / 46,13 | 43,34 / 39,00 |
| AES-GCM ARM, tag 128 bit | 36,59 / 37,75 | 34,74 / 36,06 | 33,96 / 33,13 |
| WireGuard, ChaCha20-Poly1305 | 114,86 / 183,80 | Non applicabile | Non applicabile |

Controllo UDP senza VPN e WireGuard con upstream 3.18: zero datagrammi persi
nelle due direzioni a 10/30/60 Mbit/s, datagrammi da 1.000 byte, 5 s.

## Affinità, RPS e MSS: iperf3 3.1.4

AES-CBC/SHA256-128 ARM:

| Impostazione | AES128 diretta / inversa |
| --- | ---: |
| Affinità automatica, RPS 0 | 44,12 / 41,94 |
| Server CPU 0, client CPU 1 | 41,75 / 43,90 |
| Server CPU 1, client CPU 0 | 43,03 / 44,27 |
| Entrambi CPU 0 | 38,96 / 39,84 |
| MSS 1200 | 39,53 / 39,84 |
| MSS 536 | 26,09 / 25,98 |
| RPS 3, breve | 48,26 / 59,73 |
| RPS 3, ripetizione 10 s | 48,41 / 51,43 |

Ripetizione RPS 3: AES192 44,22/45,17, AES256 44,09/39,15.
WireGuard: RPS 0 127,19/123,07; RPS 3 112,32/192,58; ripetizione
113,23/195,29. Affinità fissa e MSS ridotto non migliorano il confronto RPS.
Nessun ottimo universale o assetto IRQ fisico dedotto da queste prove.

## Pool host, rekey e UDP

Patch lab 002: pool 64/128/256, default 64; scansione lineare della lista libera
rimossa. Invariati 64 descrittori SA, ring firmware da 256 e registri.
UDP 3 s, 10 Mbit/s, datagrammi 1.000 byte, dopo cambio chiavi:

| AES | Pool 64, persi / inviati | Pool 256, persi / inviati |
| --- | ---: | ---: |
| 128 | 1305 / 3639 | 3 / 3644 |
| 192 | 1272 / 3638 | 0 / 3638 |
| 256 | 1291 / 3638 | 0 / 3639 |

Nel pool 64 ogni perdita coincide con `lab_no_slot`. Nel pool 256 contatori
no-slot/TX/recycle/double-free a zero; i tre datagrammi residui non sono
attribuiti al driver. Il pool maggiore riduce il problema riprodotto, ma non
risolve gli stalli TCP. Ping frammentati prima/dopo rekey completati.

Bundle Actions senza copie, UDP 10 s per direzione, rekey e ping frammentati:

| AES | Diretta, persi / inviati | Inversa, persi / inviati |
| --- | ---: | ---: |
| 128 | 0 / 12388 | 0 / 12513 |
| 192 | 2 / 12400 | 5 / 12520 |
| 256 | 2 / 12388 | 4 / 12513 |

Contatori diagnostici e bad-tag a zero. Queste misure precedono i controlli
upstream 3.18: le perdite dello strumento non provano da sole un errore crypto.

## Stalli TCP e sequenza dei recuperi

| Fase | Osservazione | Recupero |
| --- | --- | --- |
| Senza copie, pool 256, sequenza 10 s | AES128 9,08/51,71; AES192 44,24/5,98; AES256 diretta 51,36, inversa ferma circa 101 s; 751 esaurimenti pool | SIGINT ai processi di test, unload normale, nessun reboot |
| AES256 isolato successivo | 48,87/51,32; 207 esaurimenti, altri errori zero | Pulizia normale; non invalida il fallimento precedente |
| Bundle f503bc0 senza copie | Stallo AES128; dopo SIGINT rimasti 4 riferimenti ibrido, 8 SPU, 12 SHA256 ARM | SSH disponibile; reboot ordinato autorizzato, ripristino verificato; nessun unload forzato |
| Copie, pool 64, poll 20 ms + drain + fallback, replay 32 | Sei direzioni da 10 s completate: AES128 44,45/50,23; AES192 20,90/40,53; AES256 37,45/41,04; 9.863 fallback/esaurimenti | Zero drop driver e pendenti, ma scarti replay: non è soluzione senza perdite |
| Stessa combinazione, replay 256 | Solo diretta 66,81; persa connettività nell'inversa, poi nuovo boot ID | Nessun reboot inviato dalla sessione; intervento esterno non confermato |

66,81 Mbit/s non è un risultato bidirezionale riuscito. Il fallback prima
dell'accodamento mescola completamenti software immediati e hardware asincroni,
con riordinamento e scarti replay. Mai usato dopo invio hardware riuscito.

### Isolamento del problema, 21 ottobre

Bundle e83e33a con nuove guardie RX di arresto/errore effettivamente caricate e
testate, non più soltanto compilate. Copie, AES128, pool 64, RPS 3, poll 20 ms,
iperf3 3.18. Software e caso fallito: richiesti 15 s/direzione; altri 10 s.

| Configurazione | Replay | Diretta / inversa | Esito |
| --- | ---: | ---: | --- |
| Solo software ARM | 256 | 56,50 / 54,66 | Completata |
| Runner, solo poll | 32 | 60,00 / 46,13 | Completata, 482 esaurimenti |
| Runner, solo poll | 256 | 57,42 / 45,61 | Completata, 361 esaurimenti |
| Runner, poll + drain | 256 | 47,13 / 43,51 | Completata, 438 esaurimenti |
| Runner, poll + fallback | 256 | 54,71 / 60,92 | Completata, 53.567 fallback; scarti replay 84 e 223 su due SA |
| Runner, poll + drain + fallback | 256 | Nessuna misura completata | Persi ping/SSH nel primo TCP, successivo reboot confermato |

Casi completati: zero pendenti, errori TX/RX, doppie liberazioni rilevate e
bad-tag, unload normale. Sono prove singole, non qualificazioni di sicurezza.
La combinazione completa fallisce anche con copie e le guardie RX non lo
impediscono. Gli script rifiutano ora drain e fallback attivi insieme prima
del caricamento: contenimento, non correzione della causa kernel.

Ultimo campione completo: uptime 21440 s, memoria disponibile 194476 kB,
4.094 fallback/esaurimenti, 25.188 RX, 32 pendenti, zero errori TX/RX/double-free.
A uptime 21442 output interrotto dopo 9.574 esaurimenti; conteggio finale dei
pendenti non ricevuto. L'ultimo campione non suggerisce memoria esaurita.
Monitor SSH e lettore filtrato `/dev/kmsg` non catturano panic.

Ritorno confermato alle **08:06:41 del 21 ottobre, Europe/Rome**, boot
`2db2518f-1aef-4f6a-866a-5efbadaebb00`, prima
`fb4d1781-a9b6-41b7-92c7-901941cdb8fa`. Log:
`print_rst_status: Last RESET due to SW reset`. Nessun reboot inviato dalla
sessione per questo caso; intervento esterno non confermato. Il reset software
non identifica il chiamante né prova un panic.

Kernel: `panic=3`, `panic_on_oops=1`, MAGIC_SYSRQ e CRASH_DUMP attivi;
NETCONSOLE/NETPOLL/PSTORE/WATCHDOG/LOCKUP_DETECTOR disabilitati. Nessun pstore,
last_kmsg o crash kernel funzionante disponibile. Sysctl non modificati.
Console boot `ttyS0,115200`: la cattura seriale è il prossimo passo utile per
distinguere lockup, panic e altro reset. L'assenza di log SSH non esclude crash.

## Peer Linux esterno, MTU e offload

Peer in container Linux sul Mac, namespace/veth e NAT circoscritti. Upstream
iperf3 salvo indicazione. Non equivale a un peer nativo sulla WAN.

| Prova | Mbit/s |
| --- | ---: |
| TCP non cifrato, peer client, verso / dal modem | 490,91 / 811,25 |
| WireGuard via namespace/NAT, MTU 1420 | Circa 12–13 nelle due direzioni |
| WireGuard MTU 1280 | 11,28 / 11,01 |
| WireGuard, checksum TX/GSO/GRO disabilitati sulle veth | 12,53 / 12,16 |
| AES128-CBC/SHA256-128 ARM | 14,14 / 13,63 |
| AES256-CBC/SHA256-128 ARM, RPS 3 | 13,94 / 14,68 |
| AES128-CBC/SHA256-128 ARM, RPS 3, ripetizione | 14,75 / 14,26 |

Invertire chi avvia l'handshake non rimuove il limite WireGuard. I primi controlli
con iperf3 del firmware erano anch'essi circa 12–13 Mbit/s. Client originato nel
root namespace e relay TCP falliti: esclusi dalle tabelle. Il collo di bottiglia
comune al percorso incapsulato non è identificato e non dimostra un limite WAN
dei cifrari. Serve un peer Linux nativo per una misura fisica attendibile.

IPsec esterno senza errori autenticazione/replay. Riferimenti NAT-T talvolta
oltre il primo tentativo di unload: successiva attesa e unload ordinario riusciti,
senza forzature o reboot. Controller limitato alle proprie SA/policy, attesa fino
a 90 s/provider. Firewall normalizzato invariato dopo i test completati, esclusi
timestamp e contatori. Container e relay della prova rimossi.

## Build remote, pacchetti ed evidenze

| Build Actions | Validazione |
| --- | --- |
| 39433551005, c3a4dae | IPK stabile 4.1.52 effettivo testato; build integrata 39448024517 con modulo byte-identico |
| 39472713533 | Primo lab compilato, precedente alle correzioni XFRM e guardie finali |
| 39475046727 | Profilo con copie riuscito, precedente a patch pool 002 |
| 39478521997, f503bc0 | Sei moduli verificati, canary/KAT/UDP passati, poi stallo TCP con riferimenti pendenti |
| 39481039995, d345307 | Consolidamento: sei moduli, checksum e guardia anti-in-place verificati; nessun IPK/pubblicazione |
| 39524956679, e83e33a | 12 moduli e quattro tool statici verificati; runtime canary, GCM AES128 bidirezionale, WireGuard TCP/UDP 30 Mbit/s passati, zero perdita UDP |

I profili lab non emettono IPK e saltano la pubblicazione. `standard_tools=true`:
musl 1.2.5, wg 1.0.20210914, iperf3 3.18 statici ARM, helper ristretti, modulo
WireGuard fissato all'artefatto validato e dipendenze GCM con ABI corrispondente.
Verificati tutti i 16 checksum, ELF ARM, vermagic 4.1.52 e assenza di interprete
dinamico nei tool. IPv6 flow-label disabilitato per gli header legacy; test IPv4.

Feed pubblicati:

- https://francyesco.github.io/GUI_ipk/kernel/4.1.52/
- https://francyesco.github.io/GUI_ipk/kernel/4.1.38/

SHA256 IPK 4.1.52 realmente testato:
`a082030e1d2f93cb17bb9f61eb7b550895d38bdc2087560d6ae677a7b7796cda`.
SHA256 IPK 4.1.38 compilato:
`7b16558dc1707a96858071a6f2c2a59c45d17daa6ba1f4015c5650476ba579e6`.
La build 4.1.38 non è validazione runtime sul modem 4.1.52.

Driver diagnostico prima del primo riavvio non richiesto:
`9288e0a42306bd5ff05e7952ab57bd333f3f4be81cd80da35467e9916b35fe27`.
Driver con guardie RX testato il 21 ottobre:
`e58d572408a1b3200789880e85d8bb4985025db975e25ea87c25b7e1fdacc3f1`.

Laboratorio integrato in `kmods-4.1.52`, storia iniziale nel tag
`archive/spu-sha256-experiments-20261020`. Due branch sperimentali già integrati
rimossi; mantenuti quelli con cambiamenti non confluiti. Build stabili per entrambi
i kernel distinte dal lab: nessun ibrido promosso su main o nei feed.

`results.csv`: 80 misure iniziali; `round2-results.csv`: 98 misure con strumento,
topologia, durata, direzione, stato e fallimenti. `round2-logs.sha256`: 27 log;
`reboot-logs.sha256`: altri 12 log. `collect-round2.py` rigenera i dati dai log
locali in `.cache/tests/spu-sha256/`; prime prove stabili in
`.cache/tests/damson-spu/`. Log grezzi non pubblicati: possono contenere credenziali.

## Ultimo ripristino verificato

Dopo l'ultimo reboot: kernel 4.1.52, nuovo boot ID, modem raggiungibile, nessun
modulo lab, namespace di prova, SA/policy XFRM root o `/tmp/spu-sha256`.
SHA256 di `hardwarecrypto` invariato:
`9db4b90177169cbad1fcc4acc6a0dedcda50cb74dd07d27ebe211525abaa9058`.
Nessun nuovo oops/panic nei log filtrati del boot recuperato, nessuna modifica
persistente nelle prove. La causa del blocco/riavvio resta aperta: i test passati
e il blocco negli script non equivalgono alla sua correzione.

## Fonti tecniche esaminate

- Forum, post principale e risposte #102, #104, #107 e #152: https://www.ilpuntotecnico.com/forum/index.php/topic,82673.msg265543.html#msg265543
- Sorgenti storici Broadcom SPU: https://github.com/LuKePicci/brcm63xx-tch-src
- Contesto della famiglia BCM63xx: https://openwrt.org/docs/techref/hardware/soc/soc.broadcom.bcm63xx

Le indicazioni della famiglia BCM63xx non provano compatibilità con questo
kernel ARM vendor. Le segnalazioni firewall/DHCP/RPF e limiti UDP del forum
non sono state risolte modificando configurazioni di produzione. Lo scenario
Windows/DHCP richiede ancora una prova con client reali.
