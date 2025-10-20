#!/usr/bin/env python
# coding: utf-8

# In[ ]:

# 1.Importaciones y Configuración Inicial

# Importación de librerías
import streamlit as st
import pandas as pd
import os
import pdfplumber
from datetime import datetime, date
import re
import pytesseract
from PIL import Image
import webbrowser

# Configuración de Streamlit
st.set_page_config(page_title="Formulario Python", layout="wide") # Configura el título de la pestaña del navegador y el diseño de la página 

# Archivo donde se guardarán las respuestas
# archivo_excel = "respuestasforms.xlsx"

# Diccionario de meses en español
meses = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

#  Inicializar session_state
st.session_state.pdfs = {}
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "Nit": "",
        "Razón Social": "",
        "Ubicación": "",
        "Teléfono Celular": "",
        "Teléfono Fijo": "",
        "Nombre del Asesor Comercial": "",
        "Correo Electrónico": "",
        "Método De Pago": "",
        "Cupo Crédito": "",
        "Plazo De Pago": "",
        "Fecha de Apertura de Crédito": "",
        "Banco": "",
        "Tipo de proveedor": ""
    }

# Definir la lista de campos de texto
campos_texto_form = [
    "Nit", "Razón Social", "Ubicación", "Teléfono Celular",
    "Teléfono Fijo", "Nombre del Asesor Comercial", "Correo Electrónico",
    "Método De Pago", "Cupo Crédito", "Plazo De Pago",
    "Fecha de Apertura de Crédito"
]

# Inicializar los estados de sesión para cada campo de texto si no existen
for campo in campos_texto_form:
    if campo not in st.session_state:
        st.session_state[campo] = ""

if "Banco" not in st.session_state:
    st.session_state["Banco"] = ""
if "Tipo de proveedor" not in st.session_state:
    st.session_state["Tipo de proveedor"] = ""

# 2. Funciones de Validación de Documentos

# FUNCIONES DE VALIDACIÓN 
def funcion_x(ruta_pdf, nit_formulario):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            page = pdf.pages[0]
            texto = page.extract_text()
            if texto and texto.strip():
                fuente = "pdfplumber"
                lineas = [line.strip() for line in texto.split("\n") if line.strip()]
            else:
                fuente = "ocr"
                img = page.to_image(resolution=300).original
                texto = pytesseract.image_to_string(img, lang="spa")
                lineas = [line.strip() for line in texto.split("\n") if line.strip()]
            if not texto: raise ValueError("El PDF del RUT está vacío incluso con OCR.")
            idx_fecha, idx_nit = (50, 3) if fuente == "pdfplumber" else (59, 3)
            if len(lineas) <= max(idx_fecha, idx_nit): raise ValueError("El RUT no tiene suficientes líneas para extraer datos.")
            SubFecha = lineas[idx_fecha][32:42]
            Subnit = lineas[idx_nit][0:18]
            fechavig = datetime.strptime(SubFecha, "%d-%m-%Y").date()
            hoy = date.today()
            if (hoy - fechavig).days > 30: raise ValueError("La fecha del RUT no está vigente.")
            nit_num = int(Subnit.replace(" ", ""))
            if nit_num != nit_formulario: raise ValueError(f"NIT formulario ({nit_formulario}) ≠ NIT PDF ({nit_num}).")
            return nit_num, fechavig
    except Exception as e:
        raise e

def funcion_camara_comercio(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            page = pdf.pages[0]
            texto = page.extract_text()
            if texto and texto.strip():
                fuente = "pdfplumber"
                lineas = [line.strip() for line in texto.split("\n") if line.strip()]
            else:
                fuente = "ocr"
                img = page.to_image(resolution=300).original
                texto = pytesseract.image_to_string(img, lang="spa")
                lineas = [line.strip() for line in texto.split("\n") if line.strip()]
            if not texto: raise ValueError("El PDF Cámara Comercio está vacío incluso con OCR.")
            indice = 3 if fuente == "pdfplumber" else 4
            if len(lineas) <= indice: raise ValueError(f"El PDF no tiene la línea {indice+1} necesaria.")
            fecha_texto = lineas[indice]
            encontrado = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", fecha_texto.lower())
            if not encontrado: raise ValueError(f"No se encontró fecha válida en la línea {indice+1}: {fecha_texto}")
            dia, mes_texto, anio = int(encontrado.group(1)), encontrado.group(2), int(encontrado.group(3))
            mes = meses.get(mes_texto)
            if not mes: raise ValueError(f"Mes no reconocido: {mes_texto}")
            fechavig = date(anio, mes, dia)
            if (date.today() - fechavig).days > 30: raise ValueError("La fecha de Cámara Comercio no está vigente.")
            return fechavig
    except Exception as e:
        raise e

def funcion_certificacion_bancolombia(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = pdf.pages[0].extract_text()
            if not texto: raise ValueError("El PDF Bancolombia está vacío.")
            patron = re.compile(r"(\d{1,2})\s*de\s*([a-zA-ZñÑ]+)\s*de\s*(\d{4})", re.IGNORECASE)
            encontrado = patron.search(texto)
            if not encontrado: raise ValueError("Fecha inválida en Bancolombia.")
            dia, mes_texto, anio = int(encontrado.group(1)), encontrado.group(2).lower(), int(encontrado.group(3))
            if mes_texto not in meses: raise ValueError(f"Mes inválido en Bancolombia: {mes_texto}")
            fechavig = date(anio, meses[mes_texto], dia)
            hoy = date.today()
            if (hoy - fechavig).days > 30: raise ValueError("La certificación Bancolombia no está vigente.")
            return fechavig, (hoy - fechavig).days, texto.split("\n")[0].strip()
    except Exception as e:
        raise e

def funcion_certificacion_davivienda(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            lineas = pdf.pages[0].extract_text().split("\n")
            if len(lineas) < 2: raise ValueError("El PDF Davivienda no tiene suficiente texto.")
            fecha_texto = lineas[1].strip()
            encontrado = re.search(r"(\d{2})/(\d{2})/(\d{4})", fecha_texto)
            if not encontrado: raise ValueError("Fecha inválida en Davivienda.")
            dia, mes, anio = int(encontrado.group(1)), int(encontrado.group(2)), int(encontrado.group(3))
            fechavig = date(anio, mes, dia)
            hoy = date.today()
            if (hoy - fechavig).days > 30: raise ValueError("La certificación Davivienda no está vigente.")
            return fechavig, (hoy - fechavig).days, fecha_texto
    except Exception as e:
        raise e

def funcion_certificacion_bogota(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = pdf.pages[0].extract_text()
            if not texto: raise ValueError("El PDF Banco de Bogotá está vacío.")
            lineas = texto.split("\n")
            if len(lineas) < 8: raise ValueError("El PDF Banco de Bogotá no tiene suficiente texto.")
            linea8 = lineas[7].strip()
            patron = re.compile(r"el\s+(\d{1,2})\s+de\s+([A-Za-záéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})", re.IGNORECASE)
            encontrado = patron.search(linea8)
            if not encontrado: raise ValueError("No se encontró fecha en Banco de Bogotá.")
            dia = int(encontrado.group(1))
            mes_texto = encontrado.group(2).lower()
            anio = int(encontrado.group(3))
            mes = meses.get(mes_texto)
            if not mes: raise ValueError(f"Mes no reconocido en Banco de Bogotá: {mes_texto}")
            fechavig = date(anio, mes, dia)
            hoy = date.today()
            dias_diferencia = (hoy - fechavig).days
            if dias_diferencia > 30: raise ValueError("La certificación Banco de Bogotá no está vigente.")
            return fechavig, dias_diferencia, linea8
    except Exception as e:
        raise e

def funcion_certificacion_colpatria(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = pdf.pages[0].extract_text()
            if not texto: raise ValueError("El PDF de Colpatria está vacío.")
            lineas = texto.split("\n")
            if len(lineas) < 6: raise ValueError("El PDF de Colpatria no tiene suficiente texto.")
            linea6 = lineas[5].strip()
            patron = re.compile(
                r"(\d{1,2})\s*(?:d[ií]as\s+de)?\s+([A-Za-záéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
                re.IGNORECASE
            )
            encontrado = patron.search(linea6)
            if not encontrado: raise ValueError("No se encontró una fecha válida en la certificación de Colpatria.")
            dia = int(encontrado.group(1))
            mes_texto = encontrado.group(2).lower()
            anio = int(encontrado.group(3))
            mes = meses.get(mes_texto)
            if not mes: raise ValueError(f"Mes no reconocido en Colpatria: {mes_texto}")
            fechavig = date(anio, mes, dia)
            hoy = date.today()
            dias_diferencia = (hoy - fechavig).days
            if dias_diferencia > 30: raise ValueError("La certificación bancaria de Colpatria no está vigente.")
            return fechavig, dias_diferencia, linea6
    except Exception as e:
        raise e

def funcion_certificacion_occidente(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = pdf.pages[0].extract_text()
            if not texto: raise ValueError("El PDF de Occidente está vacío.")
            lineas = texto.split("\n")
            if len(lineas) < 8: raise ValueError("El PDF de Occidente no tiene suficiente texto.")
            linea8 = lineas[7].strip()
            patron_fecha = re.compile(
                r"hoy\s+(\d{1,2})\s+de\s+([A-Za-záéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
                re.IGNORECASE
            )
            encontrado = patron_fecha.search(linea8)
            if not encontrado: raise ValueError("No se encontró una fecha válida en la certificación de Occidente.")
            dia = int(encontrado.group(1))
            mes_texto = encontrado.group(2).lower()
            anio = int(encontrado.group(3))
            mes = meses.get(mes_texto)
            if not mes: raise ValueError(f"Mes no reconocido en Occidente: {mes_texto}")
            fechavig = date(anio, mes, dia)
            hoy = date.today()
            dias_diferencia = (hoy - fechavig).days
            if dias_diferencia > 30: raise ValueError("La certificación bancaria de Occidente no está vigente.")
            return fechavig, dias_diferencia, linea8
    except Exception as e:
        raise e

# 3.Funciones de Manejo de Datos y Envío

# Guardar respuestas
def guardar_respuestas(datos):
    df = pd.DataFrame([datos])
    if os.path.exists(archivo_excel):
        df_existente = pd.read_excel(archivo_excel)
        df = pd.concat([df_existente, df], ignore_index=True)
    df.to_excel(archivo_excel, index=False)
    st.success("¡Respuestas guardadas con éxito!")
    st.json(datos)

# Guardar PDFs temporales
def guardar_pdfs_temporales():
    rutas = {}

    nit = st.session_state.get("form_data", {}).get("Nit", "Sin NIT")

    carpeta_nit = os.path.join("temp", str(nit))
    os.makedirs(carpeta_nit, exist_ok=True)

    for tipo_doc, archivos in st.session_state.pdfs.items():
        if isinstance(archivos, list):
            rutas_lista = []
            for archivo_subido in archivos:
                if hasattr(archivo_subido, 'seek'):
                    try:
                        ruta_pdf = os.path.join(carpeta_nit, f"{tipo_doc}_{archivo_subido.name}")
                        with open(ruta_pdf, "wb") as f:
                            f.write(archivo_subido.getbuffer())
                        rutas_lista.append(ruta_pdf)
                    except Exception as e:
                        st.error(f"Error al procesar el archivo {archivo_subido.name}: {e}")
            rutas[tipo_doc] = rutas_lista
        elif archivos is not None:
            if hasattr(archivos, 'seek'):
                try:
                    ruta_pdf = os.path.join(carpeta_nit, f"{tipo_doc}_{archivos.name}")
                    with open(ruta_pdf, "wb") as f:
                        f.write(archivos.getbuffer())
                    rutas[tipo_doc] = [ruta_pdf]  # Guardar como una lista para consistencia
                except Exception as e:
                    st.error(f"Error al procesar el archivo {archivos.name}: {e}")

    return rutas

def enviar_y_ejecutar():
    try:
        nit_formulario = int(st.session_state.get("Nit"))
    except (ValueError, KeyError):
        st.error("El NIT debe ser un número válido.")
        return

    if not st.session_state.pdfs.get("RUT (PDF)"):
        st.error("Debe subir el PDF del RUT.")
        return
    if not st.session_state.pdfs.get("Cámara De Comercio (PDF)"):
        st.error("Debe subir el PDF de Cámara de Comercio.")
        return
    if not st.session_state.pdfs.get("Certificación Bancaria (PDF)"):
        st.error("Debe subir el PDF de Certificación Bancaria.")
        return
    if not st.session_state.get("Banco"):
        st.error("Debe seleccionar un banco.")
        return

    rutas_pdf = guardar_pdfs_temporales()

    try:
        
        funcion_x(rutas_pdf.get("RUT (PDF)")[0], nit_formulario)
        funcion_camara_comercio(rutas_pdf.get("Cámara De Comercio (PDF)")[0])
        banco = st.session_state.get("Banco")
        ruta_cert = rutas_pdf.get("Certificación Bancaria (PDF)")[0]

        if banco == "Bancolombia":
            funcion_certificacion_bancolombia(ruta_cert)
        elif banco == "Davivienda":
            funcion_certificacion_davivienda(ruta_cert)
        elif banco == "Banco de Bogotá":
            funcion_certificacion_bogota(ruta_cert)
        elif banco == "Colpatria":
            funcion_certificacion_colpatria(ruta_cert)
        elif banco == "Banco de Occidente":
            funcion_certificacion_occidente(ruta_cert)

    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return

    datos_para_guardar = {}
    for campo in campos_texto_form:
        datos_para_guardar[campo] = st.session_state.get(campo, "")

    datos_para_guardar["Banco"] = st.session_state.get("Banco", "")
    datos_para_guardar["Tipo de proveedor"] = st.session_state.get("Tipo de proveedor", "")

    for key, archivo in st.session_state.pdfs.items():
        if isinstance(archivo, list) and archivo:
            # Si es una lista y no está vacía, guarda el nombre del primer archivo
            datos_para_guardar[key] = archivo[0].name
        elif archivo:
            # Si es un solo archivo, guarda su nombre
            datos_para_guardar[key] = archivo.name
        else:
            # Si no hay archivo, guarda una cadena vacía
            datos_para_guardar[key] = ""

    guardar_respuestas(datos_para_guardar)
    st.success("Formulario enviado y archivos guardados correctamente.")

# 4. INTERFAZ DE USUARIO

def crear_campo_pdf(label, tipo_proveedor, multiple=False):
    key = f"{tipo_proveedor}_{label}".replace(" ", "_").replace("/", "_").replace("ñ", "n")
    return st.file_uploader(label, type=["pdf"], key=key, accept_multiple_files=multiple)


st.title("Formulario de Proveedores")

# CAMPOS DE TEXTO 
for campo in campos_texto_form:
    st.text_input(campo, key=campo)

st.session_state.pdfs["Cédula del Representante (PDF)"] = st.file_uploader(
    "Subir cédula representante (PDF)", type="pdf", key="cedula_representante"
)

#  Subida de PDFs obligatorios
st.markdown("RUT")
st.markdown("El RUT debe estar actualizado, con una fecha de generación no mayor a 30 días y reflejar la información vigente del contribuyente.")
st.session_state.pdfs["RUT (PDF)"] = st.file_uploader(
    "Subir RUT (PDF)", type="pdf", key="rut_pdf"
)
st.markdown("Cámara De Comercio")
st.markdown("Debe presentar el certificado de existencia y representación legal expedido por la Cámara de Comercio, con una fecha de expedición no mayor a 30 días.")
st.session_state.pdfs["Cámara De Comercio (PDF)"] = st.file_uploader(
    "Subir Cámara de Comercio (PDF)", type="pdf", key="camara_comercio"
)

# SELECCIÓN DE BANCO
st.selectbox(
    "Seleccione el banco",
    ["", "Bancolombia", "Davivienda", "Banco de Bogotá", "Colpatria", "Banco de Occidente"],
    key="Banco"
)
st.markdown("Certificación Bancaria")
st.markdown("Debe presentar la certificación bancaria con una fecha de expedición no mayor a 30 días.")
st.session_state.pdfs["Certificación Bancaria (PDF)"] = st.file_uploader(
    "Subir Certificación Bancaria (PDF)", type="pdf", key="cert_bancaria"
)

# TIPO DE PROVEEDOR 
opciones_tipo = [
    "Persona natural servicios administrativos",
    "Persona natural servicios operativos (mantenimiento técnicos y locativos)",
    "Empresas de Servicios administrativos",
    "Suministro de productos químicos",
    "Proveedores de productos y repuestos",
    "Equipos de computo",
    "Mantenimiento de impresoras",
    "Servicios de Seguridad y Salud en el Trabajo",
    "Exámenes médicos ocupacionales",
    "Mantenimiento de instalaciones eléctricas",
    "Mantenimiento de extintores",
    "Dotaciones",
    "Elementos de Protección Personal",
    "Transporte de carga",
    "Control de plagas y desinfección",
    "Mantenimiento de locaciones",
    "Trabajos con alturas",
    "Servicio de aseo y desinfección",
    "Dispositor de Residuos peligrosos",
    "Centro de Diagnostico Automotriz",
    "Laboratorios Diesel y Taller automotriz de mantenimiento vehicular",
    "Lavadero",
    "Empresas de seguridad física",
    "Empresas de medición o calibración",
    "Fabricación de estructuras de carrocería",
    "Empresas de Marketing",
    "Caracterización de aguas residuales",
    "Licencias Tecnológicas"
]
seleccion = st.selectbox("Seleccione el tipo de proveedor", opciones_tipo)
st.session_state["Tipo de proveedor"] = seleccion

# CAMPOS ADICIONALES POR TIPO DE PROVEEDOR 
if seleccion == "Persona natural servicios administrativos":
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados de Experiencia ({seleccion})"] = crear_campo_pdf("Certificados de Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad y/o Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad y/o Acreditación", seleccion)

elif seleccion == "Persona natural servicios operativos (mantenimiento técnicos y locativos)":
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Fichas de Seguridad Químicos ({seleccion})"] = crear_campo_pdf("Fichas de Seguridad Químicos", seleccion, multiple=True)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales / Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados de Experiencia ({seleccion})"] = crear_campo_pdf("Certificados de Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad y/o Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad y/o Acreditación", seleccion)

elif seleccion == "Empresas de Servicios administrativos":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Programas De Capacitacion Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas De Capacitacion Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados De Idoneidad y/o Acreditacion ({seleccion})"] = crear_campo_pdf("Certificados De Idoneidad Y/O Acreditacion", seleccion)

elif seleccion == "Suministro de productos químicos":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas De Seguridad químicos ({seleccion})"] = crear_campo_pdf("Fichas De Seguridad químicos", seleccion,multiple=True)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas De Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas De Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)

elif seleccion == "Proveedores de productos y repuestos":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas De Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas De Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

elif seleccion == "Equipos de computo":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificación de Disposición de Residuos ({seleccion})"] = crear_campo_pdf("Certificación de Disposición de Residuos", seleccion)

elif seleccion == "Mantenimiento de impresoras":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Plan de Manejo de Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan de Manejo de Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificación de Disposición de Residuos ({seleccion})"] = crear_campo_pdf("Certificación de Disposición de Residuos", seleccion)

elif seleccion == "Servicios de Seguridad y Salud en el Trabajo":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Certificados de Experiencia ({seleccion})"] = crear_campo_pdf("Certificados de Experiencia", seleccion)

elif seleccion == "Exámenes médicos ocupacionales":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificados de Experiencia ({seleccion})"] = crear_campo_pdf("Certificados de Experiencia", seleccion)

elif seleccion == "Mantenimiento de instalaciones eléctricas":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Matriz De identificación De Peligros ({seleccion})"] = crear_campo_pdf("Matriz De identificación De Peligros", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Matriz de Elementos de Protección Personal ({seleccion})"] = crear_campo_pdf("Matriz de Elementos de Protección Personal", seleccion)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados de Experiencia ({seleccion})"] = crear_campo_pdf("Certificados de Experiencia", seleccion)

elif seleccion == "Mantenimiento de extintores":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas De Seguridad químicos ({seleccion})"] = crear_campo_pdf("Fichas De Seguridad químicos", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificación de Disposición de Residuos ({seleccion})"] = crear_campo_pdf("Certificación de Disposición de Residuos", seleccion)

elif seleccion == "Dotaciones":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)

elif seleccion == "Elementos de Protección Personal":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)

elif seleccion == "Transporte de carga":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Matriz De identificación De Peligros ({seleccion})"] = crear_campo_pdf("Matriz De identificación De Peligros", seleccion)
    st.session_state.pdfs[f"Evidencias Del Cumplimiento del PESV ({seleccion})"] = crear_campo_pdf("Evidencias Del Cumplimiento del PESV", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificado Revision Tecnicomecanica ({seleccion})"] = crear_campo_pdf("Certificado Revision Tecnicomecanica", seleccion)
    st.session_state.pdfs[f"Certificados De Disposición De Cambio De Aceites Y Mantenimientos ({seleccion})"] = crear_campo_pdf("Certificados De Disposición De Cambio De Aceites Y Mantenimientos", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

elif seleccion == "Control de plagas y desinfección":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Matriz De identificación De Peligros ({seleccion})"] = crear_campo_pdf("Matriz De identificación De Peligros", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Matriz De Elementos De Protección Personal ({seleccion})"] = crear_campo_pdf("Matriz De Elementos De Protección Personal", seleccion)
    st.session_state.pdfs[f"Fichas De Seguridad químicos ({seleccion})"] = crear_campo_pdf("Fichas De Seguridad químicos", seleccion, multiple=True)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Concepto Favorable ({seleccion})"] = crear_campo_pdf("Concepto Favorable", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

elif seleccion == "Mantenimiento de locaciones":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Matriz De identificación De Peligros ({seleccion})"] = crear_campo_pdf("Matriz De identificación De Peligros", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Matriz De Elementos De Protección Personal ({seleccion})"] = crear_campo_pdf("Matriz De Elementos De Protección Personal", seleccion)
    st.session_state.pdfs[f"Fichas De Seguridad químicos ({seleccion})"] = crear_campo_pdf("Fichas De Seguridad químicos", seleccion, multiple=True)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificación de Disposición de Residuos ({seleccion})"] = crear_campo_pdf("Certificación de Disposición de Residuos", seleccion)

elif seleccion == "Trabajos con alturas":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados De Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados De Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Servicio de aseo y desinfección":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Matriz De identificación De Peligros ({seleccion})"] = crear_campo_pdf("Matriz De identificación De Peligros", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Matriz De Elementos De Protección Personal ({seleccion})"] = crear_campo_pdf("Matriz De Elementos De Protección Personal", seleccion)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

elif seleccion == "Dispositor de Residuos peligrosos":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificados De Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados De Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Centro de Diagnostico Automotriz":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)

elif seleccion == "Laboratorios Diesel y Taller automotriz de mantenimiento vehicular":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificados De Disposición De Cambio De Aceites Y Mantenimientos ({seleccion})"] = crear_campo_pdf("Certificados De Disposición De Cambio De Aceites Y Mantenimientos", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

elif seleccion == "Lavadero":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Programas de Capacitación Ambiental al Personal ({seleccion})"] = crear_campo_pdf("Programas de Capacitación Ambiental al Personal", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificados De Disposición De Cambio De Aceites Y Mantenimientos ({seleccion})"] = crear_campo_pdf("Certificados De Disposición De Cambio De Aceites Y Mantenimientos", seleccion)

elif seleccion == "Empresas de seguridad física":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Seguridad Social ({seleccion})"] = crear_campo_pdf("Seguridad Social", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales con soportes o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales con soportes o Certificado ISO 14001", seleccion)

elif seleccion == "Empresas de medición o calibración":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales con soportes o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales con soportes o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Fabricación de estructuras de carrocería":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Fichas Tecnicas ({seleccion})"] = crear_campo_pdf("Fichas Tecnicas", seleccion, multiple=True)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales con soportes o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales con soportes o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Empresas de Marketing":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Caracterización de aguas residuales":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Procedimiento de la Actividad a Realizar ({seleccion})"] = crear_campo_pdf("Procedimiento de la Actividad a Realizar", seleccion)
    st.session_state.pdfs[f"Inducción SST ({seleccion})"] = crear_campo_pdf("Inducción SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales con soportes o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales con soportes o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales ({seleccion})"] = crear_campo_pdf("Plan De Manejo De Residuos Convencionales, Peligrosos Y/O Especiales", seleccion)
    st.session_state.pdfs[f"Certificación de Disposición de Residuos ({seleccion})"] = crear_campo_pdf("Certificación de Disposición de Residuos", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)
    st.session_state.pdfs[f"Certificados de Idoneidad Y/O Acreditación ({seleccion})"] = crear_campo_pdf("Certificados de Idoneidad Y/O Acreditación", seleccion)

elif seleccion == "Licencias Tecnológicas":
    st.session_state.pdfs[f"Certificado De Arl Cumplimient SG-SST ({seleccion})"] = crear_campo_pdf("Certificado De Arl Cumplimient SG-SST", seleccion)
    st.session_state.pdfs[f"Buenas Prácticas Ambientales o Certificado ISO 14001 ({seleccion})"] = crear_campo_pdf("Buenas Prácticas Ambientales o Certificado ISO 14001", seleccion)
    st.session_state.pdfs[f"Certificados De Experiencia ({seleccion})"] = crear_campo_pdf("Certificados De Experiencia", seleccion)

# Agregar la información y el enlace debajo del campo de carga
st.markdown("Formato Único de Creación de Proveedores")
st.markdown("Diligenciar el siguiente formato: https://drive.google.com/file/d/1lSqtmdmTbRrOc3mGKCEJ5eISLasj4VwB/view?usp=drive_link")

st.session_state.pdfs["Formato Único de Creación de Proveedores (PDF)"] = st.file_uploader(
    "Subir Formato Único de Creación de Proveedores (PDF)", type="pdf", key="formato_proveedores"
)

# BOTÓN ENVIAR
if st.button("Enviar Formulario"):
    enviar_y_ejecutar()

