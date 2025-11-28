import streamlit as st
import pandas as pd
import re
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="Cotizador de Precios - Clientes", layout="wide")

# --- DATA LOADING & PREPROCESSING ---
@st.cache_data
def load_data():
    # Load the provided CSV file
    df = pd.read_csv('BASE PRODUCTOS COTIZADOR.xlsx - BASEPRODUCTOS.csv')
    return df

df = load_data()

# Helper Functions for Logic
def parse_hp(hp_str):
    """Parses HP strings like '1/4HP', '7 1/2 HP', '10HP' into float."""
    try:
        hp_str = hp_str.lower().replace('hp', '').strip()
        if ' ' in hp_str:  # Mixed fraction "7 1/2"
            parts = hp_str.split()
            if len(parts) == 2:
                whole = float(parts[0])
                num, den = parts[1].split('/')
                return whole + (float(num) / float(den))
        if '/' in hp_str:
            num, den = hp_str.split('/')
            return float(num) / float(den)
        return float(hp_str)
    except:
        return None

def get_transmission_category(hp):
    """Determines transmission category based on motor HP."""
    if 0.25 <= hp <= 2:
        return '0.25-2HP'
    elif 3 <= hp <= 5:
        return '3-5HP'
    elif 7.5 <= hp <= 10:
        return '7.5-10HP'
    elif 15 <= hp <= 30:
        return '15-30HP'
    return None

# --- PRE-CALCULATE MOTOR & TRANSMISSION TABLES ---
# 1. Process Motors
motors_list = []
motor_rows = df[df['CATEGORIA'].isin(['MONOFASICO', 'TRIFASICO'])]
for _, row in motor_rows.iterrows():
    match = re.search(r'(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s*HP', row['PRODUCTO'], re.IGNORECASE)
    if match:
        hp_str = match.group(1)
        hp_val = parse_hp(hp_str)
        if hp_val:
            motors_list.append({
                'hp_val': hp_val,
                'hp_display': hp_str + " HP",
                'phase': row['CATEGORIA'],  # MONOFASICO / TRIFASICO
                'price': row['Precio Publico'],
                'currency': row['Moneda'],
                'desc': row['PRODUCTO']
            })
motor_df = pd.DataFrame(motors_list)

# 2. Process Transmissions
trans_list = []
trans_cats = ['0.25-2HP', '3-5HP', '7.5-10HP', '15-30HP']
trans_rows = df[df['CATEGORIA'].isin(trans_cats)]
for _, row in trans_rows.iterrows():
    # RPM range is in PRODUCTO column like "301 a 400"
    try:
        rpm_txt = row['PRODUCTO'].lower().replace(' a ', '-').strip()
        min_rpm, max_rpm = map(int, rpm_txt.split('-'))
        trans_list.append({
            'category': row['CATEGORIA'],
            'min_rpm': min_rpm,
            'max_rpm': max_rpm,
            'price': row['Precio Publico'],
            'currency': row['Moneda']
        })
    except:
        continue
trans_df = pd.DataFrame(trans_list)

# --- SIDEBAR: PROJECT DATA ---
st.sidebar.header("📁 Datos del Proyecto")
project_name = st.sidebar.text_input("Nombre del Proyecto")
location = st.sidebar.text_input("Ciudad / Estado")
phone = st.sidebar.text_input("Celular de Contacto")

if 'cart' not in st.session_state:
    st.session_state['cart'] = []

# --- MAIN AREA: PRODUCT SELECTION ---
st.title("Calculadora de Precios")
st.markdown("---")

col1, col2 = st.columns([1, 2])

# Filter out Motor and Transmission categories from the main selection
exclude_cats = ['MONOFASICO', 'TRIFASICO'] + trans_cats
main_categories = [c for c in df['CATEGORIA'].unique() if c not in exclude_cats]

with col1:
    st.subheader("Selección de Equipo")
    category = st.selectbox("Categoría", sorted(main_categories))
    
    # Filter models by category
    models_in_cat = df[df['CATEGORIA'] == category]['Modelo'].unique()
    model = st.selectbox("Modelo", sorted(models_in_cat))
    
    # Get selected row
    item_row = df[(df['CATEGORIA'] == category) & (df['Modelo'] == model)].iloc[0]
    base_price = item_row['Precio Publico']
    currency = item_row['Moneda']
    description = item_row['PRODUCTO']

# --- LOGIC: MULTICURVA VS STANDARD ---
final_price = 0
final_description = ""
item_details = {}

with col2:
    st.subheader("Configuración y Precio")
    
    if category == 'MULTICURVA':
        st.info("🛠️ Este equipo requiere configuración de Motor y Transmisión.")
        
        c1, c2, c3 = st.columns(3)
        
        # 1. Motor Selection
        with c1:
            # Get unique HPs available in motor database
            available_hps = sorted(motor_df['hp_val'].unique())
            hp_options = {val: motor_df[motor_df['hp_val']==val]['hp_display'].iloc[0] for val in available_hps}
            selected_hp_val = st.selectbox("Potencia Motor", options=available_hps, format_func=lambda x: hp_options[x])
            
        with c2:
            phase = st.radio("Alimentación", ["MONOFASICO", "TRIFASICO"])
            
        with c3:
            rpm = st.number_input("R.P.M. Requeridas", min_value=301, max_value=2600, value=1000, step=50)

        # --- Calculations ---
        
        # A. Find Motor Price
        motor_match = motor_df[
            (motor_df['hp_val'] == selected_hp_val) & 
            (motor_df['phase'] == phase)
        ]
        
        motor_price = 0
        if not motor_match.empty:
            motor_price = motor_match.iloc[0]['price']
            st.success(f"✅ Motor: ${motor_price:,.2f}")
        else:
            st.error("❌ No existe motor con esa combinación (HP/Fase).")
            
        # B. Find Transmission Price
        trans_cat = get_transmission_category(selected_hp_val)
        trans_price = 0
        
        if trans_cat:
            trans_match = trans_df[
                (trans_df['category'] == trans_cat) & 
                (trans_df['min_rpm'] <= rpm) & 
                (trans_df['max_rpm'] >= rpm)
            ]
            if not trans_match.empty:
                trans_price = trans_match.iloc[0]['price']
                st.success(f"✅ Transmisión ({trans_cat}): ${trans_price:,.2f}")
            else:
                st.warning("⚠️ No se encontró transmisión para esas RPM en este rango de potencia.")
        else:
            st.warning("⚠️ Potencia fuera de rango para cálculo automático de transmisión.")

        # C. Total
        final_price = base_price + motor_price + trans_price
        
        # Update Description
        base_desc = description.replace("NO INCLUYE MOTOR NI TRANSMISION", "").strip()
        if base_desc.endswith("."): base_desc = base_desc[:-1]
        final_description = f"{base_desc}. INCLUYE MOTOR DE {hp_options[selected_hp_val]} {phase} Y TRANSMISIÓN PARA {rpm} RPM."
        
        st.markdown("---")
        st.write(f"**Precio Equipo Base:** ${base_price:,.2f}")
        st.write(f"**Precio Motor:** ${motor_price:,.2f}")
        st.write(f"**Precio Transmisión:** ${trans_price:,.2f}")
        
    else:
        # Standard Category
        final_price = base_price
        final_description = description
        st.write(f"**Descripción:** {final_description}")

    # --- DISPLAY FINAL PRICE ---
    st.markdown(f"### Precio Unitario: ${final_price:,.2f} {currency}")
    
    # Add Quantity
    qty = st.number_input("Cantidad", min_value=1, value=1)
    total_line_price = final_price * qty
    
    if st.button("🛒 Agregar a la Cotización"):
        if category == 'MULTICURVA' and motor_price == 0:
            st.error("No se puede agregar: Verifique selección de motor.")
        else:
            st.session_state['cart'].append({
                "Modelo": model,
                "Descripción": final_description,
                "Cantidad": qty,
                "Precio Unit.": final_price,
                "Total": total_line_price,
                "Moneda": currency
            })
            st.success("¡Agregado exitosamente!")

# --- CART SUMMARY ---
st.markdown("---")
st.header("📋 Resumen de Solicitud")

if len(st.session_state['cart']) > 0:
    cart_df = pd.DataFrame(st.session_state['cart'])
    
    # Display Table
    st.dataframe(cart_df, use_container_width=True)
    
    # Calculate Totals by Currency
    totals = cart_df.groupby('Moneda')['Total'].sum()
    
    col_tot, col_send = st.columns([1, 1])
    
    with col_tot:
        st.subheader("Total Estimado")
        for currency, amount in totals.items():
            st.markdown(f"**{currency}:** ${amount:,.2f}")
            
    with col_send:
        # Generate Mailto Link
        email_subject = f"Solicitud de Compra - {project_name}"
        
        email_body = f"""
        Hola, me gustaría realizar el siguiente pedido:
        
        DATOS DEL CLIENTE:
        Proyecto: {project_name}
        Ubicación: {location}
        Teléfono: {phone}
        
        DETALLE DEL PEDIDO:
        """
        
        for item in st.session_state['cart']:
            email_body += f"\n- ({item['Cantidad']}) {item['Modelo']}: {item['Descripción']} | ${item['Total']:,.2f} {item['Moneda']}"
            
        email_body += "\n\nQuedo atento a su confirmación."
        
        # Encode for URL
        mailto_link = f"mailto:tucorreo@ejemplo.com?subject={urllib.parse.quote(email_subject)}&body={urllib.parse.quote(email_body)}"
        
        st.markdown(f"""
            <a href="{mailto_link}" target="_blank">
                <button style="background-color:#FF4B4B;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;cursor:pointer;">
                    ✉️ Enviar Solicitud por Correo
                </button>
            </a>
            """, unsafe_allow_html=True)
            
    if st.button("Limpiar Cotización"):
        st.session_state['cart'] = []
        st.rerun()
        
else:
    st.info("No has agregado partidas a tu cotización.")
