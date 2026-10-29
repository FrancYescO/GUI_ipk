# SPU e AES-CBC per OpenVPN: verifica del 29 ottobre 2026

La correzione delle dipendenze OPKG è pubblicata con la PR #39. Interessa
tutti gli 830 IPK kernel: i `.ko` sono invariati, mentre i metadati distinguono
moduli installabili, funzionalità builtin e candidate in staging. Questa
correzione non aggiunge accelerazione a OpenVPN.

## Risultato della verifica del driver

Il driver BCM63138 `spudd/impl3` disponibile nei due SDK non implementa il
percorso AES-CBC richiesto da cryptodev/OpenSSL. Non è stata pubblicata una
modifica funzionale del driver né dichiarato accelerato OpenVPN.

Sono stati esaminati i sorgenti dei due SDK già utilizzati dalle build:

* `bcmopen-iopsys-DG400`, usato per i profili 4.1.38;
* Broadcom 502L07, usato per ricostruire il profilo 4.1.52.

Gli hash dei tre file esaminati e l'inventario delle interfacce sono conservati
in `build/spu-cbc/bcmopen-dg400-source.json` e `sdk502l07-source.json`.
Il rapporto identifica le interfacce sorgente; non certifica capacità del silicio
o del firmware Runner.

In entrambi i sorgenti:

1. `spu_algs[]` registra nomi `authenc(hmac(...),cbc(aes))`, non `cbc(aes)`.
2. L'AEAD implementa `.givencrypt` e `.decrypt`, senza `.encrypt`. Il commento
   originale accanto alla registrazione dichiara esplicitamente:
   `/*.encrypt is not supported iv is always generated */`.
3. `spu_runner_descr_config()` richiede SHA1, SHA256 oppure MD5 e rifiuta gli
   altri casi. L'helper RDPA dichiara anche checksum nell'enum, ma lo switch
   implementato non lo accetta; non espone un modo `auth_none`.
4. `rdpa_ipsec_sa_desc_setting()` configura il descrittore ESP. La firma non
   contiene un IV fornito dal chiamante; il percorso upstream abilita il RNG.

Queste osservazioni non dimostrano che il silicio sia incapace di AES-CBC puro.
Dimostrano che il percorso necessario non è esposto dall'API vendor esaminata.
Il bit `HMAC_DIS` da solo non costituisce una prova di supporto senza hash né
di compatibilità con l'IV di OpenSSL.

## Riscontro sui modem

Su `.45` e `.204` è stato caricato temporaneamente il rispettivo `bcmspu.ko`
già validato, dopo averne verificato l'hash contro l'IPK del repository. Con
`blog_offload=N` e dopo `spuctl start`, `/proc/crypto` mostrava nove algoritmi
combinati del modulo `bcmspu`. Il nome autonomo `cbc(aes)` continuava a essere
fornito da `cbc(aes-generic)` nel kernel.

Questa sessione ha verificato la registrazione degli algoritmi, senza inviare
traffico crittografico: i contatori SPU sono rimasti a zero. `spuctl stop` e
`rmmod bcmspu` hanno ripristinato lo stato iniziale. I boot ID sono rimasti:

| Modem | Boot ID | SHA256 del modulo verificato |
| --- | --- | --- |
| `.45` | `582beddd-f2cb-462b-aa09-42ba6b8bb93a` | `f5280ce13913803daf53ad500b55b478ecd5575fa0014323471223ab329016b1` |
| `.204` | `4a080e58-76b2-4210-92d6-bc6898322bbc` | `ef7a375495c71c4ff0d484856e1c7dbf9d737b9d5613aca7d2dfff3eb5e3a697` |

Sul `.69` non è stato sostituito il cryptodev stock, utilizzato da servizi del
firmware. La lettura corrente di `/proc/crypto` mostra anch'essa
`cbc(aes-generic)`; SPU non risultava caricato, mentre cryptodev aveva due
riferimenti attivi. Le precedenti prove IPsec AES/SHA1 con contatori SPU in incremento
rimangono valide; non provano accelerazione OpenVPN. Le prove OpenSSL/cryptodev
riportate nella chat DumaOS avevano già mostrato dati corretti e contatori SPU
invariati.

## Cosa occorre per una modifica funzionale

Per esporre correttamente `cbc(aes)` nella Crypto API occorre prima dimostrare
un percorso Runner che rispetti l'IV richiesto dal chiamante, le lunghezze e
i byte arbitrari di un messaggio CBC, in entrambe le direzioni. Occorre anche
risolvere l'obbligo di autenticazione/framing ESP: tramite un'interfaccia nativa
senza autenticazione, se documentata, oppure tramite un adattatore interno
verificato. Quest'ultimo avrebbe costi di copie e autenticazione aggiuntivi.

Solo dopo tale prova ha senso implementare il provider ablkcipher, la gestione
delle richieste asincrone e dei buffer, e la selezione tramite cryptodev. La sola
registrazione di un nome o l'instradamento al fallback software non risolvono
il requisito di accelerazione.

La validazione deve confrontare vettori AES-128/192/256-CBC con IV scelto dal
chiamante, cifratura e decifratura, messaggi di uno e più blocchi, operazioni
in-place e separate, aggiornamento dell'IV e limiti delle richieste. Devono
seguire contatori hardware, traffico OpenVPN bidirezionale e misure CPU/throughput.
Le precedenti prove sperimentali di adattatori AEAD avevano anche osservato
stalli sotto carico: la gestione di coda, completamento e teardown va verificata
prima di promuovere un eventuale nuovo percorso nei feed.

## Riproducibilità

Con un SDK estratto dalle sorgenti fissate dal relativo profilo CI:

```sh
python scripts/audit-spu-cbc.py /percorso/sdk > spu-capabilities.json
```

Per i sorgenti modificati dalle patch della build:

```sh
python scripts/audit-spu-cbc.py /percorso/sdk \
  --module-source /percorso/modulo-spu > spu-capabilities.json
```

Lo script funziona anche con Python 2.7 del container SDK originale. Le build
SPU manuali dei tre profili runtime lo eseguono dopo le patch e conservano il
rapporto negli artifact CI. Le build 4.1.38 archiviate precedenti non sono state
ricompilate da questa indagine. Il rapporto conserva gli hash dei sorgenti
effettivamente esaminati e non abilita alcun algoritmo sul modem.
