import pandas as pd
import json
import sys

def analyze_excel(file_path):
    try:
        xls = pd.ExcelFile(file_path)
        summary = {"hojas": xls.sheet_names, "detalle": {}}
        
        for sheet_name in xls.sheet_names:
            try:
                # Leer solo los primeros 5 registros para obtener la estructura y forma rápido
                df = pd.read_excel(xls, sheet_name=sheet_name, nrows=5)
                # Obtenemos el total real de filas de forma ligera si es posible, si no, lo saltamos
                # Para un conteo total real tendríamos que leer la hoja completa.
                # Lo leeremos completo solo para la info base.
                df_full = pd.read_excel(xls, sheet_name=sheet_name)
                
                summary["detalle"][sheet_name] = {
                    "total_filas": len(df_full),
                    "total_columnas": len(df.columns),
                    "columnas": list(df.columns),
                    "ejemplo_primera_fila": df.iloc[0].to_dict() if not df.empty else {}
                }
            except Exception as e:
                summary["detalle"][sheet_name] = {"error": str(e)}
        
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    file_path = "E:\\COLOMBIA\\PQRS_V2\\Consolidado Reclamos.xlsx"
    analyze_excel(file_path)
