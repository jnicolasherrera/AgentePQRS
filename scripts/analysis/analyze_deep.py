import pandas as pd
import json

def deep_analyze_and_save():
    file_path = "E:\\COLOMBIA\\PQRS_V2\\Consolidado Reclamos.xlsx"
    xls = pd.ExcelFile(file_path)
    
    important_sheets = ["Reclamos", "Mails", "Rtas"]
    
    analysis = "# 📊 Análisis Profundo de Datos Originales (Consolidado Reclamos)\n\n"
    
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        total_rows = len(df)
        analysis += f"## 📑 Hoja: `{sheet}`\n"
        analysis += f"- **Total de Registros:** {total_rows}\n"
        analysis += f"- **Total de Columnas:** {len(df.columns)}\n"
        
        if sheet in important_sheets:
            analysis += f"### Columnas Principales:\n"
            for col in df.columns:
                nulos = df[col].isnull().sum()
                porcentaje_nulos = round((nulos / total_rows) * 100, 2) if total_rows > 0 else 0
                analysis += f"- `{col}`: {nulos} nulos ({porcentaje_nulos}%)\n"
            
            # Si hay una columna de estado, saquemos distribución
            estado_cols = [c for c in df.columns if "ESTADO" in c.upper() or "AVANCE" in c.upper()]
            if estado_cols:
                for ecol in estado_cols:
                    dist = df[ecol].value_counts().to_dict()
                    analysis += f"### Distribución de '{ecol}':\n```json\n{json.dumps(dist, indent=2, ensure_ascii=False)}\n```\n"

        analysis += "\n---\n"
        
    with open("E:\\COLOMBIA\\Boveda_IA\\Analisis_Datos_Consolidado_Completos.md", "w", encoding="utf-8") as f:
        f.write(analysis)
        
    print("Análisis escrito exitosamente en Analisis_Datos_Consolidado_Completos.md")

if __name__ == "__main__":
    deep_analyze_and_save()
