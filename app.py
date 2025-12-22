import streamlit as st
import json
import os
import time
import random
import string
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# =========================
# Files (local persistence)
# =========================
ROOMS_FILE = "rooms.json"
STATS_FILE = "stats.json"
QUESTIONS_JSON = "questions.json"  # optional external DB (recommended when you grow to 1000+)

# =========================
# Models
# =========================
@dataclass
class Question:
    category: str
    prompt: str
    options: Dict[str, str]  # keys A/B/C/D
    answer: str              # "A"/"B"/"C"/"D"

# =========================
# Helpers
# =========================
def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def new_room_code(n=6):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def ensure_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    if room_code not in rooms:
        rooms[room_code] = {
            "created_at": int(time.time()),
            "seed": random.randint(1, 10**9),
            "players": {},  # name -> {"answers": {idx: "A"}, "done": bool}
            "result_saved": False,  # to prevent double-count
        }
        _save_json(ROOMS_FILE, rooms)

def get_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    return rooms.get(room_code)

def upsert_room(room_code: str, room_data: dict):
    rooms = _load_json(ROOMS_FILE, {})
    rooms[room_code] = room_data
    _save_json(ROOMS_FILE, rooms)

def update_stats(winner: str, loser: str, tie: bool = False):
    stats = _load_json(STATS_FILE, {})
    for name in {winner, loser}:
        if not name:
            continue
        stats.setdefault(name, {"wins": 0, "losses": 0, "ties": 0, "games": 0})

    if tie:
        stats[winner]["ties"] += 1
        stats[loser]["ties"] += 1
        stats[winner]["games"] += 1
        stats[loser]["games"] += 1
    else:
        stats[winner]["wins"] += 1
        stats[loser]["losses"] += 1
        stats[winner]["games"] += 1
        stats[loser]["games"] += 1

    _save_json(STATS_FILE, stats)

def leaderboard_rows():
    stats = _load_json(STATS_FILE, {})
    rows = []
    for name, s in stats.items():
        rows.append((name, s["wins"], s["losses"], s["ties"], s["games"]))
    rows.sort(key=lambda x: (x[1], -x[2], x[4]), reverse=True)  # wins desc, losses asc-ish, games desc
    return rows

def safe_pick_balanced(bank: List[Question], seed: int, n_total: int = 10):
    """
    Balanced pick target:
      - 4 eléctrica
      - 3 electrónica
      - 3 general
    If not enough questions in a category, fill from remaining pool.
    Deterministic by seed.
    """
    rng = random.Random(seed)
    by_cat = {"Eléctrica": [], "Electrónica": [], "General": []}
    others = []
    for q in bank:
        if q.category in by_cat:
            by_cat[q.category].append(q)
        else:
            others.append(q)

    for k in by_cat:
        rng.shuffle(by_cat[k])
    rng.shuffle(others)

    want = {"Eléctrica": 4, "Electrónica": 3, "General": 3}
    picked = []

    # pick per category
    for cat, cnt in want.items():
        picked.extend(by_cat[cat][:cnt])

    # fill remainder if needed
    if len(picked) < n_total:
        remaining = []
        # leftovers from the same cats
        for cat in want:
            remaining.extend(by_cat[cat][want[cat]:])
        remaining.extend(others)
        rng.shuffle(remaining)
        picked.extend(remaining[: (n_total - len(picked))])

    # final shuffle to mix categories
    rng.shuffle(picked)
    return picked[:n_total]

def normalize_question_dict(q: dict) -> Optional[Question]:
    try:
        category = str(q["category"]).strip()
        prompt = str(q["prompt"]).strip()
        options = q["options"]
        answer = str(q["answer"]).strip().upper()
        # basic validation
        if not isinstance(options, dict):
            return None
        # Force A/B/C/D
        keys = ["A", "B", "C", "D"]
        if any(k not in options for k in keys):
            return None
        if answer not in keys:
            return None
        return Question(category=category, prompt=prompt, options={k: str(options[k]) for k in keys}, answer=answer)
    except Exception:
        return None

def load_question_bank() -> List[Question]:
    """
    If questions.json exists, load it (recommended for 1000+).
    Otherwise, use the embedded bank below.
    """
    external = _load_json(QUESTIONS_JSON, None)
    bank: List[Question] = []

    if isinstance(external, list) and external:
        for item in external:
            if isinstance(item, dict):
                q = normalize_question_dict(item)
                if q:
                    bank.append(q)
        if len(bank) >= 50:
            return bank  # good enough external DB

    # fallback to embedded DB
    return EMBEDDED_BANK.copy()

def compute_score(questions: List[Question], answers: Dict[str, str]) -> int:
    score = 0
    for i, q in enumerate(questions):
        a = (answers.get(str(i)) or "").upper().strip()
        if a == q.answer:
            score += 1
    return score

# =========================
# Embedded question bank (mixto)
# You can grow this, or better: create questions.json with 1000+ items.
# =========================
EMBEDDED_BANK: List[Question] = []

def add_q(cat, prompt, A, B, C, D, ans):
    EMBEDDED_BANK.append(
        Question(cat, prompt, {"A": A, "B": B, "C": C, "D": D}, ans)
    )

# --- Eléctrica (varias) ---
add_q("Eléctrica", "¿Unidad de la resistencia eléctrica?", "Ohm (Ω)", "Volt (V)", "Ampere (A)", "Watt (W)", "A")
add_q("Eléctrica", "En AC senoidal, potencia activa:", "P=V·I", "P=V·I·cosφ", "P=I²·X", "P=V²·R", "B")
add_q("Eléctrica", "¿Qué protege un interruptor termomagnético?", "Sobretensión", "Fuga a tierra", "Sobrecarga y cortocircuito", "Armónicos", "C")
add_q("Eléctrica", "En paralelo, ¿qué es igual en todas las ramas?", "Corriente", "Voltaje", "Resistencia", "Potencia", "B")
add_q("Eléctrica", "¿Instrumento para medir corriente?", "Voltímetro", "Amperímetro", "Ohmímetro", "Wattímetro", "B")
add_q("Eléctrica", "¿Qué mide Hz?", "Frecuencia", "Energía", "Resistencia", "Potencia", "A")
add_q("Eléctrica", "Potencia trifásica (balanceada) usando magnitudes de línea:", "P=V_L·I_L", "P=3·V_F·I_F", "P=√3·V_L·I_L·cosφ", "P=√3·V_F·I_F", "C")
add_q("Eléctrica", "¿Qué significa FP (factor de potencia) en AC senoidal?", "P/S", "Q/S", "P/Q", "V/I", "A")
add_q("Eléctrica", "¿Qué dispositivo se usa para elevar o bajar tensión en AC?", "Rectificador", "Transformador", "Variador VFD", "Batería", "B")
add_q("Eléctrica", "¿Qué protege un interruptor diferencial (RCD)?", "Sobrecarga", "Cortocircuito", "Fuga a tierra", "Sobretensión", "C")
add_q("Eléctrica", "En serie, la corriente:", "Se divide", "Es igual en todos los elementos", "Es cero", "Depende solo del voltaje", "B")
add_q("Eléctrica", "¿Qué unidad corresponde a energía eléctrica?", "W", "Wh o kWh", "V", "A", "B")
add_q("Eléctrica", "En un motor, ¿qué equipo típicamente protege por sobrecarga prolongada?", "Relé térmico", "SPD", "Transformador", "Rectificador", "A")
add_q("Eléctrica", "¿Qué es un SPD?", "Protección contra sobretensiones transitorias", "Interruptor diferencial", "Protección contra sobrecarga", "Transformador de corriente", "A")
add_q("Eléctrica", "En una instalación, el conductor PE se asocia a:", "Fase", "Neutro", "Tierra de protección", "Control", "C")
add_q("Eléctrica", "¿Qué relación es correcta?", "1 kW = 100 W", "1 kW = 1000 W", "1 kW = 10,000 W", "1 kW = 1 W", "B")
add_q("Eléctrica", "La caída de tensión en un conductor aumenta si:", "Baja la corriente", "Aumenta la resistencia o la corriente", "Disminuye la longitud", "Aumenta la sección", "B")
add_q("Eléctrica", "¿Cuál es la función principal del neutro?", "Conducir potencia reactiva", "Referencia y retorno en sistemas monofásicos", "Protección contra rayos", "Aumentar el FP", "B")
add_q("Eléctrica", "¿Qué es una puesta a tierra?", "Aislar un circuito", "Conectar a tierra para seguridad/estabilidad", "Elevar tensión", "Convertir AC a DC", "B")
add_q("Eléctrica", "¿Qué significa 'cortocircuito'?", "Demasiada resistencia", "Camino de muy baja impedancia", "Voltaje nulo siempre", "Falta de neutro", "B")

# --- Electrónica ---
add_q("Electrónica", "¿Qué componente almacena energía en un campo eléctrico?", "Inductor", "Resistencia", "Capacitor", "Diodo", "C")
add_q("Electrónica", "Un diodo ideal conduce:", "En ambos sentidos", "Solo en un sentido", "Solo AC", "Solo señales digitales", "B")
add_q("Electrónica", "¿Qué dispositivo amplifica señales típicamente?", "Fusible", "Transistor", "Capacitor", "Bobina", "B")
add_q("Electrónica", "¿Qué hace un regulador de voltaje?", "Mantiene voltaje estable", "Aumenta la frecuencia", "Duplica potencia", "Elimina todo ruido", "A")
add_q("Electrónica", "GND normalmente es:", "Fase", "Neutro", "Referencia/tierra del circuito", "Protección SPD", "C")
add_q("Electrónica", "¿Qué mide un multímetro en modo continuidad?", "Frecuencia", "Si hay camino eléctrico (baja R)", "Potencia activa", "Factor de potencia", "B")
add_q("Electrónica", "¿Qué hace un rectificador?", "Convierte AC a DC", "Convierte DC a AC", "Eleva tensión AC", "Aísla señal", "A")
add_q("Electrónica", "Un capacitor en DC ideal en estado estable se comporta como:", "Corto", "Abierto", "Resistencia fija", "Fuente", "B")
add_q("Electrónica", "Una bobina (inductor) en DC ideal en estado estable se comporta como:", "Abierto", "Corto", "Diodo", "Transformador", "B")
add_q("Electrónica", "LED significa:", "Light Emitting Diode", "Low Energy Device", "Linear Electronic Driver", "Logic Enabled Diode", "A")
add_q("Electrónica", "¿Qué hace un filtro pasa-bajos?", "Deja pasar altas", "Deja pasar bajas y atenúa altas", "Convierte AC a DC", "Amplifica", "B")
add_q("Electrónica", "¿Qué es PWM?", "Control por modulación de ancho de pulso", "Medición de potencia media", "Protección por sobrecorriente", "Transformación de voltaje", "A")
add_q("Electrónica", "Un ADC convierte:", "Analógico a digital", "Digital a analógico", "AC a DC", "DC a AC", "A")
add_q("Electrónica", "Un DAC convierte:", "Analógico a digital", "Digital a analógico", "AC a DC", "DC a AC", "B")
add_q("Electrónica", "¿Qué es un osciloscopio?", "Medidor de potencia", "Visualiza señales en el tiempo", "Protector de sobretensión", "Medidor de aislamiento", "B")
add_q("Electrónica", "¿Qué significa 'pull-up' en digital?", "Resistencia a Vcc para definir '1' por defecto", "Bajar voltaje", "Filtro de ruido", "Rectificador", "A")
add_q("Electrónica", "¿Qué hace un amplificador operacional (op-amp) ideal en lazo cerrado?", "Satura siempre", "Amplifica según red de realimentación", "Rectifica", "Filtra solo", "B")
add_q("Electrónica", "En lógica TTL/CMOS, un '1' lógico representa:", "Nivel bajo", "Nivel alto", "Corriente cero", "Frecuencia alta", "B")
add_q("Electrónica", "¿Qué es un fusible electrónico (PTC resettable)?", "Protección que se 'resetea' al enfriar", "Transformador", "Rectificador", "Capacitor", "A")

# --- General (cultura + ciencia/tech) ---
add_q("General", "¿Cuántos bits tiene 1 byte?", "4", "8", "16", "32", "B")
add_q("General", "¿Símbolo químico del cobre?", "Co", "Cu", "Cr", "Cb", "B")
add_q("General", "¿Qué planeta tiene el campo magnético más fuerte del sistema solar?", "Marte", "Tierra", "Júpiter", "Venus", "C")
add_q("General", "¿Quién fue clave en experimentos de electromagnetismo?", "Darwin", "Faraday", "Galileo", "Bohr", "B")
add_q("General", "¿Qué unidad mide la presión?", "Pascal (Pa)", "Newton (N)", "Joule (J)", "Watt (W)", "A")
add_q("General", "¿Qué significa CPU?", "Central Processing Unit", "Control Power Unit", "Core Program Utility", "Circuit Protection Unit", "A")
add_q("General", "¿Qué es “IoT”?", "Internet of Things", "Input of Time", "Interface of Tools", "Internal of Tech", "A")
add_q("General", "¿Cuál es el océano más grande?", "Atlántico", "Índico", "Pacífico", "Ártico", "C")
add_q("General", "¿Qué mide un termómetro?", "Presión", "Temperatura", "Humedad", "Velocidad", "B")
add_q("General", "¿Qué significa GPS?", "Global Positioning System", "General Power Supply", "Graphical Position Sensor", "Ground Pressure System", "A")
add_q("General", "¿Qué gas respiramos en mayor proporción?", "Oxígeno", "Nitrógeno", "CO2", "Helio", "B")
add_q("General", "¿Cuál es la capital de Ecuador?", "Guayaquil", "Quito", "Cuenca", "Manta", "B")
add_q("General", "¿Qué mide un luxómetro?", "Flujo luminoso", "Iluminancia", "Potencia", "Corriente", "B")
add_q("General", "¿Qué significa URL?", "Uniform Resource Locator", "Universal Relay Logic", "User Request List", "Ultra Rapid Link", "A")
add_q("General", "¿Qué es “open source”?", "Software de pago", "Código abierto", "Solo para empresas", "Solo offline", "B")
add_q("General", "¿Cuál es la velocidad aproximada de la luz en el vacío?", "300,000 km/s", "30,000 km/s", "3,000 km/s", "3,000,000 km/s", "A")
add_q("General", "¿Qué instrumento mide humedad relativa?", "Barómetro", "Higrómetro", "Manómetro", "Anemómetro", "B")
add_q("General", "¿Qué significa AI en inglés?", "Artificial Intelligence", "Automatic Input", "Analog Interface", "Applied Internet", "A")

# (Puedes seguir agregando preguntas con add_q(...). Ideal: migrar a questions.json y crecer a 1000+.)

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Trivia 2 jugadores ⚡", page_icon="⚡", layout="centered")
st.title("⚡ Trivia a distancia (2 jugadores)")
st.caption("Misma sala = mismas 10 preguntas. Respuestas ocultas hasta el final 😄")

# Sidebar leaderboard
with st.sidebar:
    st.subheader("🏆 Ranking burrit@ (histórico)")
    rows = leaderboard_rows()
    if rows:
        for i, (name, w, l, t, g) in enumerate(rows[:25], start=1):
            st.write(f"**{i}. {name}** — ✅ {w} | ❌ {l} | 🤝 {t} | 🎮 {g}")
        worst = sorted(rows, key=lambda x: (x[2], x[4]), reverse=True)[0]
        st.info(f"🐴 Burrit@ oficial (más derrotas): **{worst[0]}** (❌ {worst[2]})")
    else:
        st.write("Aún no hay partidas registradas.")

st.divider()

tab1, tab2 = st.tabs(["🎮 Jugar", "📌 Instrucciones WhatsApp"])

with tab1:
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Crear sala")
        if st.button("➕ Crear nueva sala"):
            room = new_room_code()
            ensure_room(room)
            st.session_state["room_code"] = room
            st.success(f"Sala creada: **{room}**")

    with colB:
        st.subheader("Unirse a sala")
        join_code = st.text_input("Room Code", value=st.session_state.get("room_code", ""), max_chars=10).strip().upper()
        if st.button("🔗 Cargar sala"):
            if not join_code:
                st.warning("Ingresa un Room Code.")
            else:
                ensure_room(join_code)
                st.session_state["room_code"] = join_code
                st.success(f"Listo. Sala: **{join_code}**")

    room_code = st.session_state.get("room_code")
    if not room_code:
        st.info("Crea una sala o únete a una usando el Room Code.")
        st.stop()

    room = get_room(room_code)
    if not room:
        st.error("No pude cargar la sala. Intenta recargar.")
        st.stop()

    st.subheader(f"🧩 Sala: {room_code}")
    st.write("Comparte este **Room Code** con tu rival por WhatsApp.")

    player_name = st.text_input("Tu nombre (el que quieras)", value=st.session_state.get("player_name", "")).strip()
    st.session_state["player_name"] = player_name
    if not player_name:
        st.warning("Escribe tu nombre para empezar.")
        st.stop()

    # init player
    room["players"].setdefault(player_name, {"answers": {}, "done": False})
    upsert_room(room_code, room)

    bank = load_question_bank()
    if len(bank) < 20:
        st.error("El banco de preguntas es muy pequeño. Agrega más preguntas (ideal 200+ / 1000+).")
        st.stop()

    # deterministic question pick per room
    questions = safe_pick_balanced(bank, seed=room["seed"], n_total=10)

    # -------------------------
    # Gameplay (answers hidden)
    # -------------------------
    room = get_room(room_code) or room
    my = room["players"].get(player_name) or {"answers": {}, "done": False}

    if my.get("done"):
        st.success("✅ Ya terminaste tus 10 preguntas. Esperando al otro jugador…")
    else:
        st.info("🕵️ Modo competencia: **NO se muestran respuestas** hasta el final.")

        for idx, q in enumerate(questions):
            st.markdown(f"### Pregunta {idx+1}/10 — _{q.category}_")
            st.write(q.prompt)

            labels = [f"{k}) {q.options[k]}" for k in ["A", "B", "C", "D"]]
            prev = (my["answers"].get(str(idx)) or "A").upper()
            default_index = ["A", "B", "C", "D"].index(prev) if prev in ["A", "B", "C", "D"] else 0

            choice_label = st.radio(
                "Elige una opción",
                labels,
                index=default_index,
                key=f"q_{idx}_{player_name}_{room_code}",
                horizontal=False
            )
            chosen_key = choice_label.split(")")[0].strip().upper()

            if st.button("✅ Confirmar respuesta", key=f"confirm_{idx}_{player_name}_{room_code}"):
                room = get_room(room_code) or room
                room["players"].setdefault(player_name, {"answers": {}, "done": False})
                my = room["players"][player_name]

                my["answers"][str(idx)] = chosen_key

                # mark done when 10 answered
                if len(my["answers"]) >= 10:
                    my["done"] = True

                room["players"][player_name] = my
                upsert_room(room_code, room)
                st.rerun()

            st.divider()

    # -------------------------
    # Room status + Final
    # -------------------------
    room = get_room(room_code) or room
    players = room.get("players", {})

    st.subheader("📣 Estado de la sala")
    if players:
        for pname, pdata in players.items():
            status = "✅ listo" if pdata.get("done") else "⌛ jugando"
            # compute score only for display (still hidden answers during play; score can be shown)
            score = compute_score(questions, pdata.get("answers", {}))
            st.write(f"- **{pname}** — {status} — Puntaje: **{score}/10**")
    else:
        st.write("Aún no hay jugadores.")

    done_players = [(pname, pdata) for pname, pdata in players.items() if pdata.get("done")]
    if len(done_players) >= 2:
        # choose 2 first by join order (dict insertion order)
        p1, d1 = done_players[0]
        p2, d2 = done_players[1]

        s1 = compute_score(questions, d1.get("answers", {}))
        s2 = compute_score(questions, d2.get("answers", {}))

        st.subheader("🏁 Resultado final")
        st.write(f"**{p1}**: {s1}/10")
        st.write(f"**{p2}**: {s2}/10")

        if s1 > s2:
            winner, loser = p1, p2
            st.success(f"🏆 Ganador: **{winner}** — 💸 **{loser}** paga la apuesta 😄")
            tie = False
        elif s2 > s1:
            winner, loser = p2, p1
            st.success(f"🏆 Ganador: **{winner}** — 💸 **{loser}** paga la apuesta 😄")
            tie = False
        else:
            winner, loser = p1, p2
            st.info("🤝 Empate — ambos pagan o hacen desempate 😄")
            tie = True

        # Save result ONCE per room
        if not room.get("result_saved", False):
            update_stats(winner=winner, loser=loser, tie=tie)
            room["result_saved"] = True
            upsert_room(room_code, room)
            st.toast("✅ Ranking actualizado automáticamente", icon="🏆")

        # =========================
        # Review (answers revealed ONLY at the end)
        # =========================
        st.subheader("🧾 Revisión final (ahora sí se muestran respuestas)")
        for i, q in enumerate(questions):
            a1 = (d1.get("answers", {}).get(str(i)) or "-").upper()
            a2 = (d2.get("answers", {}).get(str(i)) or "-").upper()
            correct = q.answer

            st.markdown(f"**{i+1}. {q.prompt}**  \n_Categoría: {q.category}_")
            st.write(f"✅ Correcta: **{correct}) {q.options[correct]}**")
            st.write(f"👤 {p1}: **{a1}**" + (f" ✅" if a1 == correct else " ❌"))
            st.write(f"👤 {p2}: **{a2}**" + (f" ✅" if a2 == correct else " ❌"))
            st.divider()

with tab2:
    st.subheader("📌 Cómo mandarle la invitación por WhatsApp")
    st.write("1) Comparte el link de esta app.\n2) Crea una sala y envía el Room Code.\n3) Ambos entran con el mismo Room Code.")
    st.code(
        "Amor ❤️, entremos a la trivia ⚡\n"
        "Link: (pega aquí el link)\n"
        "Room Code: ABC123\n"
        "Regla: 10 preguntas, el que pierde paga 😄",
        language="text"
    )

    st.subheader("📚 Banco de preguntas grande (1000+)")
    st.write(
        "Este app **soporta** un archivo `questions.json` (recomendado) para crecer a 1000+ preguntas sin tocar el código.\n"
        "Formato: lista de objetos con `category`, `prompt`, `options` (A/B/C/D) y `answer`."
    )
    st.code(
        """[
  {
    "category": "Eléctrica",
    "prompt": "¿Qué protege un interruptor diferencial (RCD)?",
    "options": {"A":"Sobrecarga","B":"Cortocircuito","C":"Fuga a tierra","D":"Sobretensión"},
    "answer": "C"
  }
]""",
        language="json"
    )
