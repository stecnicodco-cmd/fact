import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import io

# 1. Base de datos inicial de proveedores (Memoria base)
if "reglas_proveedores" not in st.session_state:
    st.session_state.reglas_proveedores = {
        "TECHNOLOGY SUPPORT SERVICES ECUADOR": {"tipo": "FACTURAS APLICAN GASTOS PERSONALES", "rubro": "comida"},
        "OTECEL": {"tipo": "FACTURAS QUE APLICAN ACTIVIDAD ECONOMICA", "rubro": "telefonia"},
        "TUTI": {"tipo": "FACTURAS QUE APLICAN ACTIVIDAD ECONOMICA", "rubro": "material"},
        "JUAN VALDEZ": {"tipo": "FACTURAS APLICAN GASTOS PERSONALES", "rubro": "comida"},
        "DIFARE": {"tipo": "FACTURAS APLICAN GASTOS PERSONALES", "rubro": "medicina"},
        "STAV": {"tipo": "FACTURAS APLICAN GASTOS PERSONALES", "rubro": "comida"},
        "LA TABLITA": {"tipo": "FACTURAS APLICAN GASTOS PERSONALES", "rubro": "comida"},
    }

# Opciones válidas solicitadas
RUBROS_DISPONIBLES = ["medicina", "comida", "telefonia", "transporte", "material"]
TIPOS_DISPONIBLES = ["FACTURAS QUE APLICAN ACTIVIDAD ECONOMICA", "FACTURAS APLICAN GASTOS PERSONALES"]

def clasificar_proveedor(razon_social):
    """Busca el proveedor en las reglas guardadas en la sesión."""
    razon_upper = razon_social.upper()
    for clave, mapeo in st.session_state.reglas_proveedores.items():
        if clave in razon_upper:
            return mapeo["tipo"], mapeo["rubro"]
    return None, None

def procesar_xml_sri(contenido_xml):
    """Parsea el XML del SRI considerando el bloque CDATA interno."""
    try:
        root = ET.fromstring(contenido_xml)
        comprobante_nodo = root.find('comprobante')
        if comprobante_nodo is None or not comprobante_nodo.text:
            return None
            
        factura_root = ET.fromstring(comprobante_nodo.text)
        
        info_trib = factura_root.find('infoTributaria')
        razon_social = info_trib.find('razonSocial').text
        estab = info_trib.find('estab').text
        pto_emi = info_trib.find('ptoEmi').text
        secuencial = info_trib.find('secuencial').text
        num_factura = f"{estab}-{pto_emi}-{secuencial}"
        
        info_fact = factura_root.find('infoFactura')
        subtotal = float(info_fact.find('totalSinImpuestos').text)
        total = float(info_fact.find('importeTotal').text)
        iva = round(total - subtotal, 2)
        
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
        return None

# --- INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Procesador Inteligente SRI", layout="wide")
st.title("📊 Procesador Automático con Clasificación Dinámica")
st.write("Sube tus XML. Si el sistema encuentra un proveedor desconocido, podrás asignarle rubro y tipo en tiempo real.")

archivos_cargados = st.file_uploader("Sube tus archivos XML", type=["xml"], accept_multiple_files=True)

if archivos_cargados:
    datos_completos = []
    proveedores_desconocidos = set()
    
    # Primera pasada: Leer todos los archivos cargados
    for archivo in archivos_cargados:
        archivo.seek(0) # Resetear lectura del archivo
        contenido = archivo.read().decode("utf-8")
        resultado = procesar_xml_sri(contenido)
        
        if resultado:
            if resultado["Tipo"] is None:
                # Si no tiene tipo, guardamos el nombre del proveedor para preguntar al usuario
                proveedores_desconocidos.add(resultado["Proveedor"])
            datos_completos.append(resultado)

    # --- SECCIÓN DE CLASIFICACIÓN DE PROVEEDORES NUEVOS ---
    if proveedores_desconocidos:
        st.warning(f"⚠️ Se encontraron {len(proveedores_desconocidos)} proveedores nuevos sin clasificar. Por favor asígnales sus valores:")
        
        # Formulario para actualizar reglas
        with st.form("formulario_clasificacion"):
            nuevas_reglas = {}
            for prov in proveedores_desconocidos:
                st.write(f"**Proveedor:** {prov}")
                col_tipo, col_rubro = st.columns(2)
                
                with col_tipo:
                    tipo_elegido = st.selectbox(f"Tipo para {prov}", options=TIPOS_DISPONIBLES, key=f"tipo_{prov}")
                with col_rubro:
                    rubro_elegido = st.selectbox(f"Rubro para {prov}", options=RUBROS_DISPONIBLES, key=f"rubro_{prov}")
                
                nuevas_reglas[prov.upper()] = {"tipo": tipo_elegido, "rubro": rubro_elegido}
                st.write("---")
                
            guardar_boton = st.form_submit_button("💾 Guardar Clasificaciones y Procesar")
            
            if guardar_boton:
                # Guardamos las nuevas reglas en la memoria de la sesión
                st.session_state.reglas_proveedores.update(nuevas_reglas)
                st.success("¡Proveedores guardados exitosamente!")
                st.rerun() # Reinicia la página para aplicar los cambios instantáneamente

    # Segunda pasada: Si todo está clasificado, mostramos las tablas y el Excel
    if datos_completos and not proveedores_desconocidos:
        # Refrescamos los datos para aplicar las reglas recién guardadas si fuera el caso
        datos_finales = []
        for archivo in archivos_cargados:
            archivo.seek(0)
            contenido = archivo.read().decode("utf-8")
            datos_finales.append(procesar_xml_sri(contenido))
            
        df_total = pd.DataFrame(datos_finales)
        
        # Separar la información según las solicitudes exactas
        df_actividad = df_total[df_total["Tipo"] == "FACTURAS QUE APLICAN ACTIVIDAD ECONOMICA"].drop(columns=["Tipo"])
        df_personales = df_total[df_total["Tipo"] == "FACTURAS APLICAN GASTOS PERSONALES"].drop(columns=["Tipo"])
        
        # Mostrar en pantalla
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
        
        # Generar Excel estructurado
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_actividad.to_excel(writer, sheet_name='Actividad Economica', index=False)
            df_personales.to_excel(writer, sheet_name='Gastos Personales', index=False)
            
        st.write("---")
        st.download_button(
            label="📥 Descargar Reporte Consolidado en Excel",
            data=output.getvalue(),
            file_name="Desglose_Facturas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
