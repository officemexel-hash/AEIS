# Klatka Faradaya — Instrukcja bezpieczeństwa dla testów RF

## ⚠️ OBOWIĄZKOWE dla trybu RF

Transmisja na częstotliwościach komórkowych (700–2700 MHz) bez licencji
jest **nielegalna** w Polsce i UE. Testy z LimeSDR w trybie RF (rogue BTS)
MUSZĄ odbywać się w zamkniętym, ekranowanym środowisku.

Tryb ZeroMQ (symulacja) **nie wymaga** klatki Faradaya.

---

## Opcja 1: Gotowa klatka Faradaya (zalecane)

### Wymagania
- Tłumienie ≥60 dB w zakresie 700 MHz – 6 GHz
- Rozmiar minimum 60×40×40 cm (na laptop + SDR + router + Pixel)
- Drzwiczki/klapa z uszczelką RF (finger stock gasket)

### Rekomendowane produkty
- **Ramsey STE3000** (~500–800 EUR) — shielded test enclosure
- **Select Fabricators RF Box** (~300–500 EUR)
- **TekBox TBTC1** (~200 EUR) — mniejsza, na same urządzenia

### Sprawdzenie tłumienia
```bash
# Przed testem — zmierz tłumienie klatki:
# 1. Umieść HackRF WEWNĄTRZ klatki, antena podłączona
# 2. Generuj sygnał z LimeSDR NA ZEWNĄTRZ:
#    srsRAN_build/srsenb --rf.device_name=lime --rf.tx_gain=10
# 3. Sprawdź czy HackRF widzi sygnał:
#    hackrf_sweep -f 700:2700 -w 1000000

# Tłumienie OK jeśli:
# - Sygnał z zewnątrz jest ≤ -80 dBm wewnątrz klatki
# - Różnica ≥60 dB między otwartą a zamkniętą klatką
```

---

## Opcja 2: DIY klatka Faradaya (budżetowa)

### Materiały
1. **Skrzynka metalowa** — aluminiowa lub stalowa, szczelnie zamykana
   - Skrzynka narzędziowa metalowa (np. Stanley) ~50 PLN
   - Skrzynka amunicyjna NATO (surplus) ~30–80 PLN
2. **Taśma miedziana EMI** z klejem przewodzącym (3M 1181/1182) ~40 PLN/rolka
3. **Uszczelka RF** — taśma z pianki metalowej lub folii miedzianej ~30 PLN
4. **Przepusty kablowe** — panel BNC/SMA z filtrem EMI (opcjonalnie)

### Budowa
1. Oczyść skrzynkę — usuń farbę z krawędzi zamykania
2. Oklej WSZYSTKIE szwy/krawędzie taśmą miedzianą EMI
3. Na zamknięciu/klapie — przyklej uszczelkę RF (ciągły pasek dookoła)
4. Przetestuj tłumienie (jak wyżej)
5. Jeśli tłumienie < 60 dB — dodaj drugą warstwę ekranowania

### Przepusty kablowe (opcjonalne)
Jeśli potrzebujesz wyprowadzić USB z klatki:
- Użyj przepustu z filtrem EMI (ferrite + shielded connector)
- Lub przejściówki z optycznym odizolowaniem (USB over fiber)
- UWAGA: każdy kabel wychodzący z klatki to potencjalna "antena"

---

## Opcja 3: Pokój ekranowany (najlepsza)

Jeśli masz dostęp do:
- Laboratorium EMC w firmie/uczelni
- Pokoju ekranowanego (anechoic chamber)
- To jest najlepsza opcja — wchodzisz z laptopem i testujesz

---

## Procedura testowa (tryb RF)

### Przygotowanie
```bash
# 1. Umieść WSZYSTKIE urządzenia wewnątrz klatki:
#    - Laptop (z LimeSDR i HackRF przez USB)
#    - Router mobilny (z kartą SIM)
#    - Pixel (z GrapheneOS)
#    - Anteny podłączone do SDR

# 2. Zamknij klatkę
# 3. Sprawdź czy urządzenia nie mają łączności z zewnętrznymi BTS:
ssh root@router 'uqmi -d /dev/cdc-wdm0 --get-serving-system'
# Powinno pokazać "no service" lub "searching" (brak zasięgu)

# 4. Dopiero teraz uruchom rogue BTS:
SYLION_BTS_MODE=rf bash sdr/rogue_bts.sh start
```

### Podczas testu
- NIE otwieraj klatki gdy LimeSDR transmituje
- Monitoruj moc Tx — nie przekraczaj -10 dBm
- Czas testu: max 30 minut na sesję

### Po teście
```bash
# 1. Wyłącz rogue BTS:
bash sdr/rogue_bts.sh stop

# 2. Poczekaj 10 sekund
# 3. Otwórz klatkę
# 4. Sprawdź czy router wrócił na legalną BTS:
ssh root@router 'uqmi -d /dev/cdc-wdm0 --get-serving-system'
```

---

## Zmienne środowiskowe

```bash
# Tryb pracy (domyślnie zmq — bezpieczny)
export SYLION_BTS_MODE=zmq     # Symulacja — BEZ RF, BEZ klatki
export SYLION_BTS_MODE=rf      # Prawdziwy RF — WYMAGA klatki

# Moc nadawania (tylko tryb RF)
export SYLION_TX_GAIN=-10      # dBm — minimum potrzebne

# Potwierdzenie klatki (safety check)
export SYLION_FARADAY_CONFIRMED=yes  # Musisz ustawić ręcznie
```

---

## Aspekty prawne (Polska/UE)

### Prawo telekomunikacyjne
- Art. 208 Prawa telekomunikacyjnego — zakaz używania urządzeń
  zakłócających w sposób zamierzony
- Kara: do 2 lat pozbawienia wolności

### Kiedy legalnie
- W klatce Faradaya / pokoju ekranowanym (brak emisji na zewnątrz)
- Na własnych urządzeniach (router z własną kartą SIM)
- W celach badawczych / pentestowych (z dokumentacją)

### Dokumentacja
Przed każdym testem RF zapisz:
1. Data, godzina, miejsce
2. Tłumienie klatki (wynik ostatniego pomiaru)
3. Lista testowanych urządzeń
4. Cel testu
5. Wyniki
