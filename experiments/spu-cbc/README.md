# CBC nativo SPU: prototipo isolato

Sul VBNT-K 4.1.52 (`.69`, BCM63138) questo prototipo ha eseguito AES-CBC
con IV del chiamante, verificato tramite vettori kernel, OpenSSL ENGINE cryptodev
e traffico OpenVPN 2.6.23 AES-128/256-CBC con SHA256. È un esperimento manuale;
non modifica i pacchetti stabili né registra il nome pubblico `cbc(aes)`.

## Modifica del percorso

Il frontend upstream Runner genera sempre l'IV. Il frontend downstream conserva
invece l'IV ricevuto: impostando `DECRYPT=0` nel descrittore e fornendo la chiave
AES diretta, esegue **cifratura CBC** anche attraverso la richiesta downstream.
Un flag privato del contesto abilita questa variante solo per il contesto di
cifratura del laboratorio. La decifratura usa il descrittore downstream normale.

Il provider `spu-cbc-lab` costruisce frame ESP privati con HMAC-SHA1 troncato a
12 byte sull'input, invia blocchi fino a 16000 byte e ricopia soltanto il payload.
Questo HMAC serve al contratto Runner; non sostituisce l'autenticazione OpenVPN.
L'IV finale viene aggiornato usando l'ultimo blocco cifrato. Anche la rotazione
128→192→256→128 è verificata; la preparazione corregge l'accumulo dei bit di
lunghezza chiave nel driver vendor. Il vecchio modo 2 usa ECB con concatenamento
software ed è mantenuto soltanto come riferimento diagnostico (molto lento).

Tutti i nomi AEAD vendor diventano `lab-*`; il fallback AEAD è disabilitato per
non mascherare una prova hardware con software CBC. Il bridge cryptodev 1.14
con patch di ownership usa un'identità separata, `/dev/crypto-cbc-lab`, minor
dinamico e permessi 0600. Accetta solo sessioni AES-CBC senza MAC, usa copie e
non dipende dai campi `task_struct` del firmware. Non sostituisce cryptodev stock.
Lo shim `LD_PRELOAD` redirige `/dev/crypto` solo nei processi di prova. Il provider
SHA1 ARM facoltativo ha nome privato e priorità 1, inferiore a quello generico.

## Prove e limiti

[results.json](validation/results.json) registra ABI, boot ID e SHA256 dei file
provati. I log pubblicati non contengono chiavi VPN. La matrice kernel comprende
AES-128/192/256, buffer separati e in-place, scatterlist non allineate, lunghezze
16/32/64/1504/16016, passaggio fra chunk e IV finale: 48 chunk per direzione,
zero errori/fallback. Le prove EVP confrontano il ciphertext con il software
su 256 KiB per chiave e direzione. OpenVPN usa due peer UDP loopback e TUN in
namespace separati: cinque ping da 1000 byte per direzione, perdita zero, con
incremento dei contatori SPU e ripristino finale, sia AES-128 che AES-256.
I contatori Runner denominati “Decryption” includono qui anche la cifratura
perché entrambi i percorsi usano il frontend downstream.

Non emerge un vantaggio generale di velocità: EVP su buffer grandi raggiunge
circa 20–21 MiB/s, mentre il software varia circa 19–24 MiB/s. Su richieste da
1408 byte il prototipo è più lento. La CPU del solo processo esclude il thread
SPU RX e non dimostra un risparmio CPU totale. Nessuna qualificazione WAN,
multisessione concorrente o lunga durata è stata completata. Il provider
serializza ogni transform e restituisce errore se occupato, senza accodamento.
Il percorso non è ancora validato sui kernel 4.1.38 o sugli altri firmware.

Durante una prova preliminare, **prima del caricamento del prototipo SPU**,
il `.69` si è riavviato dopo richieste ioctl negative al cryptodev stock 1.6.
L'ioctl preciso non è identificato. Quel test è stato ritirato; tutte le prove
successive usano esclusivamente il bridge privato e richieste positive. I log
di successo hanno boot ID invariato `f5f36629-c02e-420f-ba8f-ed6632ac1f57`.

## Riproduzione CI

Avviare manualmente il workflow **VBNT-K 4.1.52 kernel-module artifacts** con
`module_set=spu-cbc-probe`. Riutilizza il kernel GPL e la configurazione ABI
pinnati, costruisce prima lo SPU stabile, poi il laboratorio separato, il canary,
il bridge e SHA1 ARM. I tool userspace usano il toolchain GCC 4.8 pubblico,
header OpenSSL 1.0.2t ufficiali e sorgente cryptodev: tutti verificati SHA256.
Le app di prova sono IPK pubblici elencati in `app-inputs.json`, estratti senza
installazione. L'artefatto separato si chiama `spu-cbc-4.1.52-vbntk-<commit>`;
`bundle.json` lega input e payload al commit. Il workflow **Isolated SPU CBC
source checks** verifica trasformazione del bridge, isolamento del tool e shim.

I tre script `build.sh`, `build-bridge.sh`, `build-armhash.sh` richiedono kernel,
SDK e ambiente del normale script `build-vbntj-kmods.sh` già preparati. Non
usare un kernel della stessa versione senza la configurazione/ABI esatta.
`baseline-bcmspu.ko` serve al confronto con il driver stabile: durante la prova
locale la sua sezione `.text` era identica alla pubblicata, SHA256
`7e2cf81339f7618e3d2b2ac32a37936dde302e6fc13f390292d513806a0a0f7d`.

Sul dispositivo già verificato, con SPU inizialmente scaricato, copiare il bundle
in una directory privata sotto `/tmp`, verificare i checksum e usare:

```sh
CBC_KAT_MAX=16016 sh ./run-probe.sh "$PWD" 4
CBC_OPENVPN=1 CBC_OPENVPN_BITS=128 sh ./run-engine.sh "$PWD" 4 arm
CBC_OPENVPN=1 CBC_OPENVPN_BITS=256 sh ./run-engine.sh "$PWD" 4 arm
```

Gli script verificano versione e ABI, caricano prima il canary e non forzano
scaricamenti: in presenza di richieste pendenti conservano i moduli dipendenti.
La prova OpenVPN richiede il TUN già validato (SHA256 controllato dallo script),
`ip netns`, `spuctl` e OpenSSL runtime 1.0.2 con engine cryptodev. Non cambia
routing/firewall o configurazioni VPN esistenti. Le build non sono IPK e non
vengono promosse automaticamente nel feed OPKG: una futura integrazione stabile
richiede conservare le API IPsec pubbliche e verificarne le regressioni.
