import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import io

# 1. Diccionario de reglas de clasificación automática (Personalizable)
# Puedes expandir este diccionario con los comercios que frecuentas
REGLAS_PROVEEDORES = {
    "TECHNOLOGY SUPPORT SERVICES ECUADOR": {"tipo": "Gastos Personales", "rubro": "Servicio Comida"}, # Ejemplo del XML subido (Ubereats/Uber)
    "OTECEL": {"tipo": "Actividad Económica", "rubro": "Telefonía"},
    "TUTI": {"tipo": "Actividad Económica", "rubro": "Limpieza"},
    "JUAN VALDEZ": {"tipo": "Gastos Personales", "rubro": "Comida"},
    "DIFARE": {"tipo": "Gastos Personales", "rubro": "Medicina"},
    "STAV": {"tipo": "Gastos Personales", "rubro": "Comida"},
    "LA TABLITA": {"tipo": "Gastos Personales", "rubro": "Comida"},
    "FLORES BORJA": {"tipo": "Actividad Económica", "rubro": "Ing Civil"},
    "ARMENDARIZ FRANCO": {"tipo": "Actividad Económica", "rubro": "Ing Civil"},
    "RENDON ONTANEDA": {"tipo": "Actividad Económica", "rubro": "Ing Civil"},
}

def clasificar_proveedor(razon_social):
    """Asigna rubro y tipo según el nombre del emisor."""
    razon_upper = razon_social.upper()
    for clave, mapeo in REGLAS_PROVEEDORES.items():
        if clave in razon_upper:
            return mapeo["tipo"], mapeo["rubro"]
    return "Por Clasificar", "Otros"

def procesar_xml_sri(contenido_xml):
    """Parsea el XML del SRI considerando el bloque CDATA interno."""
    try:
        root = ET.fromstring(contenido_xml)
        
        # El XML del SRI tiene la factura dentro de <comprobante> como CDATA
        comprobante_nodo = root.find('comprobante')
        if comprobante_nodo is None or not comprobante_nodo.text:
            return None
            
        factura_root = ET.fromstring(comprobante_nodo.text)
        
        # Extracción de datos de InfoTributaria
        info_trib = factura_root.find('infoTributaria')
        razon_social = info_trib.find('razonSocial').text
        estab = info_trib.find('estab').text
        pto_emi = info_trib.find('ptoEmi').text
        secuencial = info_trib.find('secuencial').text
        num_factura = f"{estab}-{pto_emi}-{secuencial}"
        
        # Extracción de datos de InfoFactura
        info_fact = factura_root.find('infoFactura')
        subtotal = float(info_fact.find('totalSinImpuestos').text)
        total = float(info_fact.find('importeTotal').text)
        iva = round(total - subtotal, 2)
        
        # Clasificación automática
        tipo_gasto, rubro = clasificar_proveedor(razon_social)
        
        return {
            "Número Factura": num_factura,
            "Rubro": rubro,
            "Proveedor": razon_social,
            "Subtotal": subtotal,
            "IVA": iva,
            "Total": total,
            "Tipo": tipo_gasto
        }
    except Exception as e:
        st.error(f"Error procesando un archivo: {e}")
        return None

# --- INTERFAZ DE USUARIO (STREAMLIT) ---
st.set_page_config(page_title="Procesador de Facturas SRI", layout="wide")
st.title("📊 Procesador Automático de XML - SRI Ecuador")
st.write("Sube tus archivos XML autorizados para generar el desglose de actividades y gastos personales.")

archivos_cargados = st.file_uploader("Sube uno o varios archivos XML", type=["xml"], accept_multiple_files=True)

if archivos_cargados:
    datos_procesados = []
    
    for archivo in archivos_cargados:
        contenido = archivo.read().decode("utf-8")
        resultado = procesar_xml_sri(contenido)
        if resultado:
            datos_procesados.append(resultado)
            
    if datos_procesados:
        df_total = pd.DataFrame(datos_procesados)
        
        # Separar en dos DataFrames según tu estructura de Excel
        df_actividad = df_total[df_total["Tipo"] == "Actividad Económica"].drop(columns=["Tipo"])
        df_personales = df_total[df_total["Tipo"] == "Gastos Personales"].drop(columns=["Tipo"])
        df_otros = df_total[df_total["Tipo"] == "Por Clasificar"].drop(columns=["Tipo"])
        
        # Mostrar Tablas en la UI
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏢 Actividad Económica")
            st.dataframe(df_actividad, use_container_width=True)
            if not df_actividad.empty:
                st.metric("Total Actividad", f"${df_actividad['Total'].sum():.2f}")
                
        with col2:
            st.subheader("🏠 Gastos Personales")
            st.dataframe(df_personales, use_container_width=True)
            if not df_personales.empty:
                st.metric("Total Gastos Personales", f"${df_personales['Total'].sum():.2f}")
                
        if not df_otros.empty:
            st.subheader("❓ Proveedores Nuevos (Sin Clasificar)")
            st.dataframe(df_otros, use_container_width=True)

        # Creación del archivo Excel en memoria con dos pestañas o secciones
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_actividad.to_excel(writer, sheet_name='Actividad Economica', index=False)
            df_personales.to_excel(writer, sheet_name='Gastos Personales', index=False)
            if not df_otros.empty:
                df_otros.to_excel(writer, sheet_name='Por Clasificar', index=False)
        
        st.write("---")
        st.download_button(
            label="📥 Descargar Reporte Consolidado en Excel",
            data=output.getvalue(),
            file_name="Desglose_Facturas_Automatico.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No se pudo extraer información válida de los XML provistos.")
