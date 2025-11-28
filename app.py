import streamlit as st
import pandas as pd
import math
import urllib.parse
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Cotizador Admin CS",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    .main-header { font-size: 28px; font-weight: bold; color: #0E4F8F; margin-bottom: 10px; }
    .price-tag { font-size: 24px; font-weight: bold; color: #28a745; }
    .profit-tag { font-size: 18px; font-weight: bold; color: #0E4F8F; background-color: #e6f2ff; padding: 5px; border-radius: 5px;}
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 5px; border: 1px solid #c3e6cb; }
    .warning-box { padding: 10px; background-color: #fff3cd; color: #856404; border-radius: 5px; border: 1px solid #ffeeba; }
    .danger-box { padding: 10px; background-color: #f8d7da; color: #721c24; border-radius: 5px; border: 1px solid #f5c6cb; }
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES DE LÓGICA ---
@st.cache_data
def load_data():
    try:
        # Intenta leer excel, si falla, csv (dependiendo de qué subiste)
        try:
            df = pd.read_excel("productos.xlsx")
        except:
            df = pd.read_csv("productos.xlsx") # En caso de que sea un csv renombrado
            
        # Limpieza básica de columnas clave
        df['CATEGORIA'] = df['CATEGORIA'].astype(str).str.strip()
        df['Modelo'] = df['Modelo'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"⚠️ Error leyendo la base de datos: {e}")
        return pd.DataFrame()

def parse_hp(hp_str):
    """Convierte texto como '1/4HP' o '7 1/2' a número flotante"""
    try:
        s = str(hp_str).lower().replace('hp', '').replace('motor', '').strip()
        if ' ' in s: # Fracción mixta "7 1/2"
            parts = s.split()
            if len(parts) == 2:
                whole = float(parts[0])
                frac_parts = parts[1].split('/')
                if len(frac_parts) == 2:
                    return whole + (float(frac_parts[0])/float(frac_parts[1]))
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

# --- 4. CARGA DE DATOS Y PREPROCESAMIENTO ---
df = load_data()

if not df.empty:
    # Crear Dataframes auxiliares para búsquedas rápidas
    
    # 1. Motores (Filtramos solo las categorías de motor)
    df_motors = df[df['CATEGORIA'].isin(['MONOFASICO', 'TRIFASICO'])].copy()
    # Extraemos el valor numérico de HP para poder buscar
    df_motors['HP_Val'] = df_motors['PRODUCTO'].apply(
        lambda x: parse_hp(re.search(r'(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s*HP', str(x), re.IGNORECASE).group(1)) 
        if re.search(r'(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s*HP', str(x), re.IGNORECASE) else 0
    )
    
    # 2. Transmisiones
    cat_trans = ["0.25-2HP", "3-5HP", "7.5-10HP", "15-30HP"]
    df_trans = df[df['CATEGORIA'].isin(cat_trans)].copy()

# --- 5. SIDEBAR: CONFIGURACIÓN DEL PROYECTO ---
with st.sidebar:
    try:
        st.image("logo.jpg", use_column_width=True)
    except:
        st.header("CS VENTILACIÓN")
    
    st.markdown("---")
    st.header("⚙️ Configuración de Precios")
    
    # SELECTOR DE TIPO DE PRECIO (NUEVO REQ)
    tipo_cliente = st.selectbox("Seleccionar Lista de Precios:", 
                                ["Publico en general", "Cliente Top LABPUE/CUL", "Costo CS ventilacion"])
    
    # Mapeo de la selección del usuario a la columna exacta del Excel
    col_precio_map = {
        "Publico en general": "Precios de Lista",
        "Cliente Top LABPUE/CUL": "Precio Contratista sin flete",
        "Costo CS ventilacion": "Precio Fabrica"
    }
    
    col_venta = col_precio_map[tipo_cliente]
    col_costo = "Precio Fabrica" # Siempre usamos esta para calcular la ganancia real
    
    st.info(f"Usando columna: **{col_venta}**")
    
    st.markdown("---")
    st.header("📁 Datos del Proyecto")
    nom_proy = st.text_input("Nombre Proyecto")
    ciudad = st.text_input("Ciudad/Estado")
    celular = st.text_input("Celular de Contacto") # NUEVO REQ
    
    st.markdown("---")
    if 'carrito' not in st.session_state: st.session_state['carrito'] = []
    
    st.markdown(f"**Carrito: {len(st.session_state['carrito'])} Partidas**")
    if st.button("🗑️ Limpiar Carrito"):
        st.session_state['carrito'] = []
        st.rerun()

# --- 6. INTERFAZ PRINCIPAL ---
st.markdown('<div class="main-header">COTIZADOR ADMINISTRATIVO</div>', unsafe_allow_html=True)

if df.empty:
    st.error("No se cargaron datos. Verifica que 'productos.xlsx' esté en GitHub.")
    st.stop()

col_sel, col_res = st.columns([1, 1.5])

with col_sel:
    st.subheader("1. Selección de Modelo")
    
    # Filtro de Categorías (Excluyendo componentes sueltos para la selección principal)
    cats_excluded = ['MONOFASICO', 'TRIFASICO', 'MOTOR'] + cat_trans
    # Nos aseguramos de mostrar solo categorías que existen en el DF
    cats_display = sorted([c for c in df['CATEGORIA'].unique() if c not in cats_excluded])
    
    categoria = st.selectbox("Categoría", cats_display)
    
    # Filtro de Modelos
    modelos_disp = sorted(df[df['CATEGORIA'] == categoria]['Modelo'].unique())
    modelo = st.selectbox("Modelo", modelos_disp)
    
    # Obtener datos del equipo base
    # Usamos iloc[0] para tomar el primer match
    row_base = df[(df['CATEGORIA'] == categoria) & (df['Modelo'] == modelo)].iloc[0]
    
    desc_base = row_base['PRODUCTO']
    moneda = row_base['Moneda']
    
    # Precios Base (Venta y Costo)
    # Usamos .get para evitar error si la columna no existe (pone 0)
    p_base_venta = row_base.get(col_venta, 0)
    p_base_costo = row_base.get(col_costo, 0)

with col_res:
    st.subheader("2. Configuración y Precio")
    
    # Variables acumuladoras para el precio final de la partida
    precio_unit_venta = p_base_venta
    precio_unit_costo = p_base_costo
    desc_final = desc_base
    error_msg = ""
    
    # --- LÓGICA ESPECÍFICA MULTICURVA ---
    if categoria == "MULTICURVA":
        st.info("🛠️ Configuración de Motor y Transmisión requerida.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            # Listar HPs disponibles
            hps_disp = sorted(df_motors['HP_Val'].unique())
            hp_sel = st.selectbox("Potencia (HP)", hps_disp, format_func=lambda x: f"{x} HP")
        with c2:
            fase_sel = st.radio("Fase", ["MONOFASICO", "TRIFASICO"])
        with c3:
            rpm_req = st.number_input("RPM", 301, 2600, 1000, 50)
            
        # A. BUSCAR MOTOR
        motor_match = df_motors[(df_motors['HP_Val'] == hp_sel) & (df_motors['CATEGORIA'] == fase_sel)]
        
        p_motor_venta = 0
        p_motor_costo = 0
        
        if not motor_match.empty:
            m_row = motor_match.iloc[0]
            p_motor_venta = m_row.get(col_venta, 0)
            p_motor_costo = m_row.get(col_costo, 0)
            st.success(f"✅ Motor: ${p_motor_venta:,.2f}")
        else:
            st.error("❌ Motor no disponible en esa fase.")
            error_msg = "Motor no encontrado"
            
        # B. BUSCAR TRANSMISIÓN
        cat_t = get_trans_cat(hp_sel)
        p_trans_venta = 0
        p_trans_costo = 0
        
        if cat_t:
            # Filtrar transmisiones de la categoría correcta
            trans_subset = df_trans[df_trans['CATEGORIA'] == cat_t]
            found_trans = False
            
            for _, t_row in trans_subset.iterrows():
                # Parsear rango RPM del texto "301 a 400"
                try:
                    txt = str(t_row['PRODUCTO']).lower().replace(' a ', '-').strip()
                    r_min, r_max = map(int, txt.split('-'))
                    
                    if r_min <= rpm_req <= r_max:
                        p_trans_venta = t_row.get(col_venta, 0)
                        p_trans_costo = t_row.get(col_costo, 0)
                        found_trans = True
                        break
                except:
                    continue
            
            if found_trans:
                st.success(f"✅ Transmisión ({cat_t}): ${p_trans_venta:,.2f}")
            else:
                st.warning(f"⚠️ Sin transmisión para {rpm_req} RPM")
        
        # SUMAR TOTALES MULTICURVA
        precio_unit_venta += (p_motor_venta + p_trans_venta)
        precio_unit_costo += (p_motor_costo + p_trans_costo)
        
        # ACTUALIZAR DESCRIPCIÓN
        desc_limpia = str(desc_base).replace("NO INCLUYE MOTOR NI TRANSMISION", "").replace(".", "")
        desc_final = f"{desc_limpia}. INCLUYE MOTOR {hp_sel} HP {fase_sel} Y TRANSMISIÓN PARA {rpm_req} RPM."

    else:
        # LÓGICA ESTÁNDAR (No Multicurva)
        st.write(f"**Descripción:** {desc_base}")
    
    # --- VISUALIZACIÓN DE PRECIOS Y GANANCIA UNITARIA ---
    st.markdown("---")
    
    # Precio de Venta
    st.markdown(f'<div class="price-tag">Precio Venta Unitario: ${precio_unit_venta:,.2f} {moneda}</div>', unsafe_allow_html=True)
    
    # Cálculo Ganancia Unitaria
    ganancia_unit = precio_unit_venta - precio_unit_costo
    
    # Mostrar Ganancia (Solo para tus ojos, visible en pantalla)
    st.markdown(f"""
    <div class="profit-tag">
        💰 Costo Unit: ${precio_unit_costo:,.2f} | Ganancia Unit: ${ganancia_unit:,.2f}
    </div>
    """, unsafe_allow_html=True)
    
    # Cantidad
    qty = st.number_input("Cantidad", 1, 100, 1)
    
    total_venta_partida = precio_unit_venta * qty
    total_costo_partida = precio_unit_costo * qty
    total_ganancia_partida = ganancia_unit * qty
    
    if st.button("🛒 Agregar al Pedido"):
        if error_msg:
            st.error(f"Error: {error_msg}")
        else:
            st.session_state['carrito'].append({
                "Modelo": modelo,
                "Descripción": desc_final,
                "Cantidad": qty,
                "Precio Unit.": precio_unit_venta,
                "Total Venta": total_venta_partida,
                "Total Costo": total_costo_partida,
                "Ganancia": total_ganancia_partida,
                "Moneda": moneda
            })
            st.success("¡Agregado!")
            st.rerun()

# --- 7. RESUMEN FINAL ---
st.markdown("---")
st.header("📋 Resumen Económico del Proyecto")

if len(st.session_state['carrito']) > 0:
    df_cart = pd.DataFrame(st.session_state['carrito'])
    
    # Mostrar tabla (Ocultamos costo y ganancia si se desea, o se deja visible para control interno)
    # Para control administrativo mostramos todo
    st.dataframe(df_cart[["Cantidad", "Modelo", "Descripción", "Precio Unit.", "Total Venta", "Ganancia", "Moneda"]], use_container_width=True)
    
    # TOTALES GENERALES
    st.markdown("### 📊 Totales por Moneda")
    
    # Agrupar por moneda
    monedas = df_cart['Moneda'].unique()
    
    for m in monedas:
        df_m = df_cart[df_cart['Moneda'] == m]
        sum_venta = df_m['Total Venta'].sum()
        sum_costo = df_m['Total Costo'].sum()
        sum_ganancia = df_m['Ganancia'].sum()
        
        c1, c2, c3 = st.columns(3)
        with c1: st.metric(f"Venta Total ({m})", f"${sum_venta:,.2f}")
        with c2: st.metric(f"Costo Total ({m})", f"${sum_costo:,.2f}")
        with c3: st.metric(f"GANANCIA ({m})", f"${sum_ganancia:,.2f}", delta="Utilidad")
        st.markdown("---")

    # Botón de Correo
    subject = f"Pedido: {nom_proy} ({ciudad})"
    body = f"""SOLICITUD DE COMPRA / COTIZACIÓN

DATOS DEL CLIENTE:
Proyecto: {nom_proy}
Ciudad: {ciudad}
Celular: {celular}
Lista de Precios Usada: {tipo_cliente}

DETALLE DEL PEDIDO:
"""
    for item in st.session_state['carrito']:
        body += f"\n- ({item['Cantidad']}) {item['Modelo']}\n  {item['Descripción']}\n  Precio Venta: ${item['Total Venta']:,.2f} {item['Moneda']}\n"
    
    # Agregar resumen de totales al correo
    body += "\nRESUMEN ECONÓMICO:\n"
    for m in monedas:
        df_m = df_cart[df_cart['Moneda'] == m]
        body += f"Total Venta ({m}): ${df_m['Total Venta'].sum():,.2f}\n"
        # (Opcional: No incluir ganancia en el texto del correo si se va a reenviar a cliente final, 
        # pero si es para ti, está bien).
    
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
        ✉️ ENVIAR SOLICITUD A VENTAS@CS
    </a>
    """, unsafe_allow_html=True)

else:
    st.info("El carrito está vacío.")
