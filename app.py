import streamlit as st
import pandas as pd
import math
import urllib.parse
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Cotizador CS Ventilación",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    .main-header { font-size: 28px; font-weight: bold; color: #0E4F8F; margin-bottom: 10px; }
    .price-tag { font-size: 24px; font-weight: bold; color: #28a745; }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 5px; border: 1px solid #c3e6cb; }
    .warning-box { padding: 10px; background-color: #fff3cd; color: #856404; border-radius: 5px; border: 1px solid #ffeeba; }
    .danger-box { padding: 10px; background-color: #f8d7da; color: #721c24; border-radius: 5px; border: 1px solid #f5c6cb; }
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES DE LÓGICA ---
@st.cache_data
def load_data():
    try:
        # Lee el archivo Excel que debes subir como 'productos.xlsx'
        df = pd.read_excel("productos.xlsx")
        # Limpieza básica
        df['CATEGORIA'] = df['CATEGORIA'].astype(str).str.strip()
        df['Modelo'] = df['Modelo'].astype(str).str.strip()
        return df
    except FileNotFoundError:
        st.error("⚠️ No se encontró el archivo 'productos.xlsx' en el repositorio.")
        return pd.DataFrame()

def parse_hp(hp_str):
    """Convierte texto como '1/4HP' o '7 1/2' a número flotante"""
    try:
        s = str(hp_str).lower().replace('hp', '').replace('motor', '').strip()
        if ' ' in s: # Fracción mixta "7 1/2"
            whole, frac = s.split()
            num, den = frac.split('/')
            return float(whole) + (float(num)/float(den))
        elif '/' in s: # Fracción simple "1/2"
            num, den = s.split('/')
            return float(num)/float(den)
        else:
            return float(s)
    except:
        return 0.0

def get_trans_cat(hp):
    """Define la categoría de transmisión según los HP"""
    if 0.25 <= hp <= 2.0: return "0.25-2HP"
    if 3.0 <= hp <= 5.0: return "3-5HP"
    if 7.5 <= hp <= 10.0: return "7.5-10HP"
    if 15.0 <= hp <= 30.0: return "15-30HP"
    return None

# --- 4. CARGA DE DATOS ---
df = load_data()

if not df.empty:
    # Separar Motores y Transmisiones para búsqueda rápida
    df_motors = df[df['CATEGORIA'].isin(['MONOFASICO', 'TRIFASICO'])].copy()
    # Extraer HP numérico para los motores
    df_motors['HP_Val'] = df_motors['PRODUCTO'].apply(lambda x: parse_hp(re.search(r'(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s*HP', str(x), re.IGNORECASE).group(1)) if re.search(r'(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s*HP', str(x), re.IGNORECASE) else 0)
    
    # Transmisiones
    cat_trans = ["0.25-2HP", "3-5HP", "7.5-10HP", "15-30HP"]
    df_trans = df[df['CATEGORIA'].isin(cat_trans)].copy()

# --- 5. SIDEBAR ---
with st.sidebar:
    try:
        st.image("logo.jpg", use_column_width=True)
    except:
        st.header("CS VENTILACIÓN")
        st.caption("Sube 'logo.jpg' al repositorio")
    
    st.markdown("---")
    st.header("📁 Datos del Proyecto")
    nom_proy = st.text_input("Nombre Proyecto")
    ciudad = st.text_input("Ciudad/Estado")
    celular = st.text_input("Celular de Contacto")
    
    st.markdown("---")
    if 'carrito' not in st.session_state: st.session_state['carrito'] = []
    
    st.markdown(f"**Carrito: {len(st.session_state['carrito'])} Partidas**")
    if st.button("🗑️ Limpiar Carrito"):
        st.session_state['carrito'] = []
        st.rerun()

# --- 6. INTERFAZ PRINCIPAL ---
st.markdown('<div class="main-header">COTIZADOR DE PRECIOS</div>', unsafe_allow_html=True)

if df.empty:
    st.stop()

col_sel, col_res = st.columns([1, 1.5])

with col_sel:
    st.subheader("1. Selección de Modelo")
    
    # Filtramos categorías "normales" (excluyendo motores y transmisiones de la lista principal)
    cats_excluded = ['MONOFASICO', 'TRIFASICO', 'MOTOR'] + cat_trans
    cats_display = sorted([c for c in df['CATEGORIA'].unique() if c not in cats_excluded])
    
    categoria = st.selectbox("Categoría", cats_display)
    
    # Filtrar modelos por categoría
    modelos_disp = sorted(df[df['CATEGORIA'] == categoria]['Modelo'].unique())
    modelo = st.selectbox("Modelo", modelos_disp)
    
    # Obtener datos base
    row_base = df[(df['CATEGORIA'] == categoria) & (df['Modelo'] == modelo)].iloc[0]
    desc_base = row_base['PRODUCTO']
    precio_base = row_base['Precio Publico']
    moneda = row_base['Moneda']

with col_res:
    st.subheader("2. Configuración y Precio")
    
    precio_final = precio_base
    desc_final = desc_base
    error_msg = ""
    
    # --- LÓGICA MULTICURVA ---
    if categoria == "MULTICURVA":
        st.info("🛠️ Este equipo se cotiza por componentes (Equipo + Motor + Transmisión).")
        
        # 1. Selección de Motor
        c1, c2 = st.columns(2)
        with c1:
            # Opciones de HP disponibles en la base de datos de motores
            hps_disp = sorted(df_motors['HP_Val'].unique())
            # Formatear para mostrar bonito (0.5 -> 1/2 HP)
            hp_sel = st.selectbox("Potencia Motor (HP)", hps_disp, format_func=lambda x: f"{x} HP")
        with c2:
            fase_sel = st.radio("Alimentación", ["MONOFASICO", "TRIFASICO"])
            
        # Buscar Motor
        motor_match = df_motors[(df_motors['HP_Val'] == hp_sel) & (df_motors['CATEGORIA'] == fase_sel)]
        
        precio_motor = 0
        if not motor_match.empty:
            motor_row = motor_match.iloc[0]
            precio_motor = motor_row['Precio Publico']
            st.success(f"✅ Motor: ${precio_motor:,.2f}")
        else:
            st.error("❌ No existe motor con esta combinación HP/Fase.")
            error_msg = "Motor no disponible"

        # 2. Selección de Transmisión
        cat_t = get_trans_cat(hp_sel)
        rpm_req = st.number_input("R.P.M. Requeridas", 301, 2600, 1000, 50)
        
        precio_trans = 0
        if cat_t:
            # Buscar rango de RPM en la descripción del producto (ej: "301 a 400")
            # Filtramos las transmisiones de la categoría correcta
            trans_subset = df_trans[df_trans['CATEGORIA'] == cat_t]
            
            found_trans = False
            for _, t_row in trans_subset.iterrows():
                # Parsear "301 a 400"
                try:
                    txt = t_row['PRODUCTO'].lower().replace(' a ', '-').strip()
                    r_min, r_max = map(int, txt.split('-'))
                    if r_min <= rpm_req <= r_max:
                        precio_trans = t_row['Precio Publico']
                        found_trans = True
                        break
                except:
                    continue
            
            if found_trans:
                st.success(f"✅ Transmisión ({cat_t}): ${precio_trans:,.2f}")
            else:
                st.warning(f"⚠️ No se encontró transmisión para {rpm_req} RPM en rango {cat_t}")
        
        # Sumatoria
        precio_final = precio_base + precio_motor + precio_trans
        
        # Reemplazar texto descriptivo
        desc_limpia = desc_base.replace("NO INCLUYE MOTOR NI TRANSMISION", "").replace(".", "")
        desc_final = f"{desc_limpia}. INCLUYE MOTOR {hp_sel} HP {fase_sel} Y TRANSMISIÓN PARA {rpm_req} RPM."

    else:
        # Lógica Estándar
        st.write(f"**Descripción:** {desc_base}")
    
    st.markdown("---")
    st.markdown(f'<div class="price-tag">Precio Unitario: ${precio_final:,.2f} {moneda}</div>', unsafe_allow_html=True)
    
    qty = st.number_input("Cantidad", 1, 100, 1)
    total_partida = precio_final * qty
    
    if st.button("🛒 Agregar al Pedido"):
        if error_msg:
            st.error(f"No se puede agregar: {error_msg}")
        else:
            st.session_state['carrito'].append({
                "Modelo": modelo,
                "Descripción": desc_final,
                "Cantidad": qty,
                "Unitario": precio_final,
                "Total": total_partida,
                "Moneda": moneda
            })
            st.success("¡Partida agregada!")
            st.rerun()

# --- 7. RESUMEN Y ENVÍO ---
st.markdown("---")
st.header("📋 Resumen del Pedido")

if len(st.session_state['carrito']) > 0:
    df_cart = pd.DataFrame(st.session_state['carrito'])
    st.dataframe(df_cart, use_container_width=True)
    
    # Totales por moneda
    st.subheader("Total Estimado")
    totales = df_cart.groupby("Moneda")["Total"].sum()
    for m, val in totales.items():
        st.markdown(f"**Total {m}:** ${val:,.2f}")
        
    # Botón de Correo
    subject = f"Pedido Web: {nom_proy}"
    body = f"""Hola, envío solicitud de compra:

CLIENTE:
Proyecto: {nom_proy}
Ubicación: {ciudad}
Celular: {celular}

DETALLE DEL PEDIDO:
"""
    for item in st.session_state['carrito']:
        body += f"\n- ({item['Cantidad']}) {item['Modelo']}\n  {item['Descripción']}\n  Total: ${item['Total']:,.2f} {item['Moneda']}\n"
    
    body += "\nQuedo atento a la confirmación."
    
    safe_sub = urllib.parse.quote(subject)
    safe_body = urllib.parse.quote(body)
    mailto = f"mailto:ventas@csventilacion.mx?subject={safe_sub}&body={safe_body}"
    
    st.markdown(f"""
    <a href="{mailto}" target="_blank" style="
        display: inline-block;
        background-color: #28a745;
        color: white;
        padding: 15px 30px;
        text-decoration: none;
        border-radius: 5px;
        font-weight: bold;
        font-size: 18px;">
        ✉️ ENVIAR PEDIDO POR CORREO
    </a>
    """, unsafe_allow_html=True)

else:
    st.info("El carrito está vacío.")
