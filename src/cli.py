"""CLI principal para el sistema LLM-DW."""

import ast
import json
import sys
from datetime import datetime
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from sqlalchemy import Engine

from src.agents.query_explainer import explain_query, explain_query_simple
from src.agents.sql_agent import create_sql_agent, execute_query
from src.schemas.database_schema import DatabaseSchema, get_schema_for_prompt, load_schema
from src.utils.database import get_db_engine, test_connection
from src.utils.exceptions import (
    DatabaseConnectionError,
    LLMDWError,
    SQLValidationError,
)
from src.utils.history import clear_history, get_history_entry, load_history, save_query
from src.utils.logger import logger
from src.utils.performance import (
    clear_performance_metrics,
    get_failed_queries,
    get_performance_stats,
    get_query_patterns,
    get_slow_queries,
    record_query_performance,
)
from src.validators.sql_validator import SQLValidator

console = Console()


class StreamingDisplay:
    """Maneja el display de streaming en tiempo real."""
    
    def __init__(self):
        self.sql = None
        self.status = "Iniciando..."
        self.data = None
        self.analysis = ""
        self.error = None
        self.layout = None
        self.live = None
    
    def update(self, chunk_info: dict):
        """Actualiza el display con información del chunk."""
        chunk_type = chunk_info.get("type")
        content = chunk_info.get("content", "")
        
        if chunk_type == "sql":
            self.sql = content
            self.status = "[cyan]Generando SQL...[/cyan]"
        elif chunk_type == "execution":
            self.status = "[green]Ejecutando query...[/green]"
            self.data = content
        elif chunk_type == "data":
            self.data = content
            self.status = "[green]Datos recibidos[/green]"
        elif chunk_type == "analysis":
            # Acumular análisis (puede venir en múltiples chunks)
            if content:
                if self.analysis:
                    self.analysis += content
                else:
                    self.analysis = content
            self.status = "[yellow]Generando análisis...[/yellow]"
        elif chunk_type == "error":
            self.error = content
            self.status = "[red]Error[/red]"
        
        # Actualizar layout si está activo
        if self.live:
            self._render()
    
    def _render(self) -> Layout:
        """Renderiza el layout actual."""
        layout = Layout()
        
        # Sección de SQL
        sql_section = Panel(
            Syntax(self.sql, "sql", theme="monokai", line_numbers=False) if self.sql 
            else Text("Generando SQL...", style="dim"),
            title="[bold cyan]SQL[/bold cyan]",
            border_style="cyan",
            padding=(0, 1)
        )
        
        # Sección de estado
        status_section = Panel(
            Text(self.status, style="white"),
            title="[bold]Estado[/bold]",
            border_style="blue",
            padding=(0, 1)
        )
        
        # Sección de datos
        data_section = Panel(
            Text(self.data[:500] + "..." if self.data and len(self.data) > 500 else (self.data or "Esperando datos..."), 
                 style="white"),
            title="[bold green]Datos[/bold green]",
            border_style="green",
            padding=(0, 1)
        )
        
        # Sección de análisis
        analysis_section = Panel(
            Text(self.analysis or "Generando análisis...", style="white"),
            title="[bold yellow]Análisis[/bold yellow]",
            border_style="yellow",
            padding=(0, 1)
        )
        
        # Sección de error si existe
        if self.error:
            error_section = Panel(
                Text(self.error, style="red"),
                title="[bold red]Error[/bold red]",
                border_style="red",
                padding=(0, 1)
            )
            layout.split_column(
                Layout(sql_section, size=8),
                Layout(status_section, size=3),
                Layout(data_section, size=6),
                Layout(analysis_section, size=6),
                Layout(error_section, size=4)
            )
        else:
            layout.split_column(
                Layout(sql_section, size=8),
                Layout(status_section, size=3),
                Layout(data_section, size=6),
                Layout(analysis_section, size=8)
            )
        
        return layout
    
    def start(self):
        """Inicia el display en modo live."""
        self.layout = self._render()
        self.live = Live(self.layout, console=console, refresh_per_second=4)
        self.live.start()
    
    def stop(self):
        """Detiene el display live."""
        if self.live:
            self.live.stop()
            self.live = None


def _display_streaming_response(question: str):
    """
    Crea y retorna un objeto StreamingDisplay para mostrar progreso en tiempo real.
    
    Args:
        question: Pregunta del usuario (para contexto)
        
    Returns:
        StreamingDisplay configurado
    """
    display = StreamingDisplay()
    display.start()
    return display


def _extract_column_names_from_sql(sql: str, num_cols: int) -> list[str] | None:
    """
    Extrae nombres de columnas del SQL generado.
    
    Args:
        sql: Query SQL
        num_cols: Número esperado de columnas
        
    Returns:
        Lista de nombres de columnas o None si no se pueden extraer
    """
    if not sql:
        return None
    
    try:
        import re
        sql_clean = sql.strip()
        
        # Buscar SELECT ... FROM (puede haber WITH antes)
        # Remover comentarios y normalizar espacios
        sql_clean = re.sub(r'--.*?$', '', sql_clean, flags=re.MULTILINE)
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
        sql_clean = ' '.join(sql_clean.split())
        
        # Buscar SELECT ... FROM (puede estar después de WITH)
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql_clean, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return None
        
        select_clause = select_match.group(1).strip()
        
        # Dividir por comas, pero respetar paréntesis y funciones
        columns = []
        current_col = ""
        paren_depth = 0
        in_quotes = False
        quote_char = None
        
        for char in select_clause:
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_col += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_col += char
            elif not in_quotes:
                if char == '(':
                    paren_depth += 1
                    current_col += char
                elif char == ')':
                    paren_depth -= 1
                    current_col += char
                elif char == ',' and paren_depth == 0:
                    if current_col.strip():
                        columns.append(current_col.strip())
                    current_col = ""
                else:
                    current_col += char
            else:
                current_col += char
        
        # Agregar última columna
        if current_col.strip():
            columns.append(current_col.strip())
        
        # Extraer nombres de columnas (después de AS o el nombre de la columna)
        headers = []
        for col in columns[:num_cols]:
            col_clean = col.strip()
            
            # Buscar alias (AS nombre) - puede estar al final
            as_match = re.search(r'\bAS\s+["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?', col_clean, re.IGNORECASE)
            if as_match:
                alias = as_match.group(1)
                # Convertir snake_case a Title Case
                header = alias.replace('_', ' ').title()
                headers.append(header)
                continue
            
            # Si es una función agregada, usar nombre descriptivo
            if re.match(r'SUM\s*\(', col_clean, re.IGNORECASE):
                # Intentar extraer nombre de columna dentro de la función
                inner_match = re.search(
                    r'SUM\s*\(\s*(?:[a-zA-Z_]+\.)?([a-zA-Z_]+)',
                    col_clean,
                    re.IGNORECASE,
                )
                if inner_match:
                    col_name = inner_match.group(1)
                    headers.append(f"Total {col_name.replace('_', ' ').title()}")
                else:
                    headers.append("Total")
            elif re.match(r'COUNT\s*\(', col_clean, re.IGNORECASE):
                headers.append("Cantidad")
            elif re.match(r'AVG\s*\(', col_clean, re.IGNORECASE):
                headers.append("Promedio")
            elif re.match(r'MAX\s*\(', col_clean, re.IGNORECASE):
                headers.append("Máximo")
            elif re.match(r'MIN\s*\(', col_clean, re.IGNORECASE):
                headers.append("Mínimo")
            elif re.match(r'DATE_TRUNC|TO_CHAR|EXTRACT', col_clean, re.IGNORECASE):
                # Funciones de fecha
                if 'month' in col_clean.lower():
                    headers.append("Mes")
                elif 'year' in col_clean.lower():
                    headers.append("Año")
                elif 'day' in col_clean.lower():
                    headers.append("Día")
                else:
                    headers.append("Fecha")
            else:
                # Extraer nombre de columna o tabla.columna
                # Remover funciones y paréntesis para encontrar el nombre base
                col_clean_no_func = re.sub(r'[A-Z_]+\s*\(', '', col_clean)
                col_clean_no_func = re.sub(r'\)', '', col_clean_no_func)
                
                # Buscar tabla.columna o solo columna
                col_name_match = re.search(r'(?:[a-zA-Z_]+\.)?([a-zA-Z_][a-zA-Z0-9_]*)', col_clean_no_func)
                if col_name_match:
                    col_name = col_name_match.group(1)
                    header = col_name.replace('_', ' ').title()
                    headers.append(header)
                else:
                    headers.append(None)
        
        # Si tenemos suficientes headers válidos, retornarlos
        if len(headers) == num_cols and all(h for h in headers):
            return headers
        
        return None
        
    except Exception:
        return None


def _export_results(data: str, sql: str | None, export_format: str, question: str) -> None:
    """
    Exporta resultados a archivo.

    Args:
        data: Datos a exportar (respuesta del agente)
        sql: SQL generado (opcional)
        export_format: Formato de exportación (csv, json, excel)
        question: Pregunta original (para nombre de archivo)
    """
    try:
        from datetime import datetime
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_question = "".join(c for c in question[:30] if c.isalnum() or c in (" ", "-", "_")).strip()
        safe_question = safe_question.replace(" ", "_")
        
        if export_format == "csv":
            filename = f"query_{safe_question}_{timestamp}.csv"
            with open(filename, "w", encoding="utf-8") as f:
                # Si hay SQL, ejecutarlo directamente para obtener datos estructurados
                # Por ahora, exportar como texto
                f.write(f"Query: {question}\n")
                if sql:
                    f.write(f"SQL: {sql}\n\n")
                f.write("Resultados:\n")
                f.write(data)
            console.print(f"[bold green]✓ Resultados exportados a:[/bold green] {filename}")
        
        elif export_format == "json":
            filename = f"query_{safe_question}_{timestamp}.json"
            export_data = {
                "question": question,
                "sql": sql,
                "timestamp": datetime.now().isoformat(),
                "results": data,
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            console.print(f"[bold green]✓ Resultados exportados a:[/bold green] {filename}")
        
        elif export_format == "excel":
            # Requiere openpyxl o xlsxwriter
            try:
                import pandas as pd
                filename = f"query_{safe_question}_{timestamp}.xlsx"
                
                # Intentar parsear datos como DataFrame si es posible
                # Por ahora, crear DataFrame simple con la respuesta
                df = pd.DataFrame({"Resultado": [data]})
                df.to_excel(filename, index=False)
                console.print(f"[bold green]✓ Resultados exportados a:[/bold green] {filename}")
            except ImportError:
                console.print("[yellow]Para exportar a Excel, instala: pip install pandas openpyxl[/yellow]")
                console.print("[dim]Exportando como CSV en su lugar...[/dim]")
                _export_results(data, sql, "csv", question)
        
        logger.info(f"Resultados exportados a {filename}")
    
    except Exception as e:
        console.print(f"[bold red]Error al exportar:[/bold red] {str(e)}")
        logger.error(f"Error en exportación: {e}")


def _infer_column_headers(data: list, num_cols: int) -> list[str]:
    """
    Infiere nombres de columnas más descriptivos basándose en los datos.
    
    Args:
        data: Lista de filas de datos
        num_cols: Número de columnas
        
    Returns:
        Lista de nombres de columnas inferidos
    """
    if not data or len(data) == 0:
        return [f"Columna {i+1}" for i in range(num_cols)]
    
    # Analizar tipos de datos en cada columna para inferir nombres
    column_types = []
    for col_idx in range(num_cols):
        sample_values = [row[col_idx] for row in data[:10] if col_idx < len(row) and row[col_idx] is not None]
        
        if not sample_values:
            column_types.append(f"Columna {col_idx + 1}")
            continue
        
        # Detectar tipo de dato
        is_numeric = all(
            isinstance(val, (int, float)) or 
            (isinstance(val, str) and val.replace('.', '').replace('-', '').replace(',', '').isdigit())
            for val in sample_values
        )
        is_id = all(
            isinstance(val, int) and val > 0 and val < 100000
            for val in sample_values
        ) and len(sample_values) > 0 and is_numeric
        
        is_large_number = any(
            (isinstance(val, (int, float)) and val > 1000) or
            (isinstance(val, str) and val.replace(',', '').replace('.', '').isdigit() and int(val.replace(',', '').replace('.', '')) > 1000)
            for val in sample_values
        )
        
        # Inferir nombre basado en posición, tipo y contexto
        if col_idx == 0:
            if is_id:
                header = "ID"
            elif is_numeric:
                header = "Valor"
            else:
                header = "Nombre / Descripción"
        elif col_idx == 1:
            if is_numeric and is_large_number:
                header = "Total Vendido"
            elif is_numeric:
                header = "Cantidad"
            else:
                header = "Descripción"
        elif col_idx == 2:
            if is_numeric and is_large_number:
                header = "Stock Actual"
            elif is_numeric:
                header = "Stock / Inventario"
            else:
                header = "Detalle"
        elif col_idx == 3:
            if is_numeric and is_large_number:
                header = "Revenue / Total"
            elif is_numeric:
                header = "Total"
            else:
                header = "Información"
        else:
            header = f"Columna {col_idx + 1}"
        
        column_types.append(header)
    
    return column_types


def _format_value(value: Any) -> str:
    """
    Formatea un valor para mostrar en la tabla.
    
    Args:
        value: Valor a formatear
        
    Returns:
        String formateado
    """
    if value is None:
        return "N/A"
    
    # Formatear números con separadores de miles
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            # Formatear decimales (máximo 2 decimales, sin ceros innecesarios)
            if value == int(value):
                return f"{int(value):,}"
            return f"{value:,.2f}"
        else:
            return f"{value:,}"
    
    # Formatear Decimal (de SQL)
    if hasattr(value, '__class__') and 'Decimal' in str(type(value)):
        try:
            decimal_val = float(value)
            if decimal_val == int(decimal_val):
                return f"{int(decimal_val):,}"
            return f"{decimal_val:,.2f}"
        except:
            return str(value)
    
    return str(value)


def _generate_automatic_analysis(data: list, sql: str | None = None, question: str = "") -> str:
    """
    Genera análisis automático basado en los datos.
    
    Args:
        data: Lista de tuplas/listas con los datos
        sql: SQL generado (opcional, para contexto)
        question: Pregunta original (opcional, para contexto)
        
    Returns:
        Análisis en lenguaje natural
    """
    if not data or len(data) == 0:
        return "No hay datos para analizar."
    
    num_rows = len(data)
    num_cols = len(data[0]) if data else 0
    
    # Extraer información básica de los datos
    analysis_parts = []
    
    # Resumen general
    analysis_parts.append(f"Se encontraron {num_rows} registros.")
    
    # Análisis de columnas numéricas
    if num_cols > 1:
        # Analizar segunda columna (típicamente cantidad/total)
        if num_cols >= 2:
            col2_values = [row[1] for row in data if len(row) > 1 and isinstance(row[1], (int, float))]
            if col2_values:
                total_col2 = sum(col2_values)
                max_col2 = max(col2_values)
                min_col2 = min(col2_values)
                avg_col2 = total_col2 / len(col2_values) if col2_values else 0
                
                # Identificar el registro con el valor máximo
                max_row = next((row for row in data if len(row) > 1 and row[1] == max_col2), None)
                max_name = max_row[0] if max_row and len(max_row) > 0 else "N/A"
                
                analysis_parts.append(
                    f"El valor máximo es {_format_value(max_col2)} ({max_name}), "
                    f"el mínimo es {_format_value(min_col2)}, "
                    f"y el promedio es {_format_value(avg_col2)}."
                )
        
        # Analizar tercera columna si existe (típicamente stock)
        if num_cols >= 3:
            col3_values = [row[2] for row in data if len(row) > 2 and isinstance(row[2], (int, float))]
            if col3_values:
                total_col3 = sum(col3_values)
                avg_col3 = total_col3 / len(col3_values) if col3_values else 0
                
                # Verificar si hay productos con stock bajo (menor al promedio)
                low_stock = [row for row in data if len(row) > 2 and isinstance(row[2], (int, float)) and row[2] < avg_col3]
                
                if low_stock:
                    analysis_parts.append(
                        f"Hay {len(low_stock)} productos con stock por debajo del promedio ({_format_value(avg_col3)}). "
                        f"Se recomienda revisar estos productos para evitar desabastecimiento."
                    )
                else:
                    analysis_parts.append(
                        f"El stock promedio es {_format_value(avg_col3)}. "
                        f"La mayoría de los productos mantienen niveles de inventario adecuados."
                    )
    
    # Insights adicionales basados en la pregunta
    if "vendidos" in question.lower() or "ventas" in question.lower():
        if num_cols >= 2:
            # Verificar si hay productos con 0 ventas
            zero_sales = [row for row in data if len(row) > 1 and isinstance(row[1], (int, float)) and row[1] == 0]
            if zero_sales:
                analysis_parts.append(
                    f"Nota: {len(zero_sales)} productos no tienen ventas registradas. "
                    f"Esto puede indicar productos nuevos o con problemas de demanda."
                )
    
    # Conclusión
    if num_rows > 0:
        analysis_parts.append(
            "En resumen, estos datos proporcionan una visión clara del estado actual. "
            "Se recomienda monitorear regularmente estos indicadores para tomar decisiones informadas."
        )
    
    return " ".join(analysis_parts)


def _format_query_result(response: str, output_format: str = "table", sql_generated: str | None = None, question: str = "") -> None:
    """
    Formatea y muestra el resultado de una query.

    Args:
        response: Respuesta del agente (puede contener datos tabulares, tuplas, listas)
        output_format: Formato de salida ('table' o 'json')
        sql_generated: SQL generado (opcional, para inferir nombres de columnas)
    """
    # Intentar parsear como estructura de Python (tuplas, listas)
    try:
        import ast
        import re
        
        # Normalizar respuesta: remover saltos de línea innecesarios dentro de listas/tuplas
        normalized_response = response.strip()
        
        # Si la respuesta parece ser una lista de tuplas con saltos de línea, limpiarla
        if normalized_response.startswith("[") and "\n" in normalized_response:
            # Remover saltos de línea y espacios extras, pero mantener estructura
            # Primero intentar parsear como está
            try:
                parsed_data = ast.literal_eval(normalized_response)
            except (ValueError, SyntaxError):
                # Si falla, limpiar saltos de línea y espacios extras
                # Mantener comas y paréntesis importantes
                cleaned = re.sub(r'\s+', ' ', normalized_response)
                cleaned = cleaned.replace(' ,', ',').replace(', ', ',')
                parsed_data = ast.literal_eval(cleaned)
        else:
            # Intentar evaluar como estructura de Python
            parsed_data = ast.literal_eval(normalized_response)
        
        # Si es una lista de tuplas o lista de listas, formatear como tabla
        if isinstance(parsed_data, list) and len(parsed_data) > 0:
            if isinstance(parsed_data[0], (tuple, list)):
                # Es una lista de filas
                table = Table(
                    show_header=True, 
                    header_style="bold cyan",
                    box="rounded",
                    show_lines=True,
                    padding=(0, 1),
                    border_style="bright_blue"
                )
                
                # Determinar número de columnas
                num_cols = len(parsed_data[0])
                
                # Intentar inferir nombres de columnas del SQL si está disponible
                headers = None
                if sql_generated:
                    headers = _extract_column_names_from_sql(sql_generated, num_cols)
                
                # Si no se pudieron extraer del SQL, inferir de los datos
                if not headers:
                    headers = _infer_column_headers(parsed_data, num_cols)
                
                # Agregar columnas con estilos apropiados
                for i, header in enumerate(headers):
                    # Determinar alineación basada en el tipo de datos
                    sample_col_values = [row[i] for row in parsed_data[:5] if i < len(row)]
                    is_numeric_col = any(
                        isinstance(val, (int, float)) or 
                        (isinstance(val, str) and val.replace('.', '').replace('-', '').replace(',', '').isdigit())
                        for val in sample_col_values
                    )
                    
                    justify = "right" if (i > 0 and is_numeric_col) else "left"
                    col_style = "bright_white" if is_numeric_col else "white"
                    
                    table.add_column(
                        header, 
                        style=col_style,
                        justify=justify,
                        overflow="fold",
                        min_width=12
                    )
                
                # Agregar filas con valores formateados
                for row in parsed_data:
                    # Formatear cada valor apropiadamente
                    formatted_row = [_format_value(val) for val in row]
                    table.add_row(*formatted_row)
                
                console.print(table)
                
                # Generar análisis automático si no hay análisis en la respuesta
                # Verificar si la respuesta original tiene texto analítico
                response_has_analysis = (
                    len(response) > len(str(parsed_data)) + 50 or  # Respuesta es más larga que solo datos
                    not response.strip().startswith("[") or  # No empieza con lista
                    "análisis" in response.lower() or
                    "conclusión" in response.lower() or
                    "insight" in response.lower()
                )
                
                if not response_has_analysis:
                    # Generar análisis automático
                    analysis = _generate_automatic_analysis(parsed_data, sql_generated, question)
                    if analysis:
                        panel = Panel(
                            Text(analysis, style="white"),
                            title="[bold cyan]Análisis[/bold cyan]",
                            border_style="cyan",
                            padding=(1, 2)
                        )
                        console.print(panel)
                
                return
            elif isinstance(parsed_data, dict):
                # Es un diccionario, mostrar como tabla de clave-valor
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Clave", style="cyan")
                table.add_column("Valor", style="white")
                for key, value in parsed_data.items():
                    table.add_row(str(key), str(value))
                console.print(table)
                return
    except (ValueError, SyntaxError, AttributeError):
        # No es una estructura de Python válida, continuar con otros formatos
        pass
    
    # Definir lines aquí antes de usarla
    lines = response.strip().split("\n")
    
    # Detectar formato tabular simple (filas con | o tabs)
    if len(lines) > 2 and any("|" in line or "\t" in line for line in lines[:5]):
        # Parsear como tabla
        table = Table(show_header=True, header_style="bold magenta")
        
        # Detectar headers (primera línea o línea con separadores)
        header_line = None
        for i, line in enumerate(lines[:10]):
            if "|" in line or "\t" in line:
                header_line = i
                break
        
        if header_line is not None:
            # Parsear headers
            if "|" in lines[header_line]:
                headers = [h.strip() for h in lines[header_line].split("|") if h.strip()]
            else:
                headers = [h.strip() for h in lines[header_line].split("\t") if h.strip()]
            
            # Agregar columnas a la tabla
            for header in headers:
                table.add_column(header, style="cyan")
            
            # Agregar filas y encontrar el final de la tabla
            table_end_idx = header_line
            for line in lines[header_line + 1:]:
                if "|" in line or "\t" in line:
                    table_end_idx += 1
                    if "|" in line:
                        row = [cell.strip() for cell in line.split("|") if cell.strip()]
                    else:
                        row = [cell.strip() for cell in line.split("\t") if cell.strip()]
                    
                    # Asegurar que el número de columnas coincida
                    if len(row) == len(headers):
                        table.add_row(*row)
                else:
                    # Fin de la tabla
                    break
            
            console.print(table)
            
            # Detectar texto analítico después de la tabla
            outro_text = "\n".join(lines[table_end_idx + 1:]).strip()
            if outro_text and len(outro_text) > 20:
                # Filtrar líneas que parecen ser parte de la tabla
                outro_lines = [l for l in outro_text.split("\n") if not ("|" in l or "┃" in l or "┏" in l or "┡" in l or "─" in l)]
                if outro_lines:
                    analysis_text = "\n".join(outro_lines)
                    panel = Panel(
                        Text(analysis_text, style="white"),
                        title="[bold cyan]Análisis[/bold cyan]",
                        border_style="cyan",
                        padding=(1, 2)
                    )
                    console.print(panel)
            return
    
    # Detectar si hay texto analítico sin tabla
    # Buscar bloques de texto analítico
    # Nota: lines ya está definida arriba
    has_table = False
    analysis_text = []
    table_start_idx = None
    table_end_idx = None
    
    # Detectar si hay estructura tabular en la respuesta (con caracteres Unicode)
    for i, line in enumerate(lines):
        if "┃" in line or "┏" in line or "┡" in line:
            if not has_table:
                table_start_idx = i
                has_table = True
            table_end_idx = i
    
    # Si hay tabla Unicode, extraer texto antes y después
    if has_table and table_start_idx is not None:
        # Texto antes de la tabla (introducción)
        intro_text = "\n".join(lines[:table_start_idx]).strip()
        if intro_text and len(intro_text) > 20:
            analysis_text.append(("intro", intro_text))
        
        # Texto después de la tabla (análisis)
        if table_end_idx is not None:
            outro_text = "\n".join(lines[table_end_idx + 1:]).strip()
            if outro_text and len(outro_text) > 20:
                # Filtrar líneas que parecen ser parte de la tabla
                outro_lines = [l for l in outro_text.split("\n") if not ("|" in l or "┃" in l or "┏" in l or "┡" in l or "─" in l)]
                if outro_lines:
                    analysis_text.append(("analysis", "\n".join(outro_lines)))
    else:
        # No hay tabla, toda la respuesta puede ser análisis
        full_text = response.strip()
        if full_text and len(full_text) > 50:
            analysis_text.append(("full", full_text))
    
    # Mostrar texto analítico si existe
    for text_type, text_content in analysis_text:
        if text_type == "intro":
            console.print(f"\n[dim italic]{text_content}[/dim italic]\n")
        elif text_type == "analysis":
            # Mostrar análisis con estilo destacado
            panel = Panel(
                Text(text_content, style="white"),
                title="[bold cyan]Análisis[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            )
            console.print(panel)
        elif text_type == "full":
            # Si no hay tabla, mostrar como texto formateado
            console.print(f"\n{text_content}\n")
    
    # Si no es tabular o formato es json, mostrar como está
    if output_format == "json":
        try:
            # Intentar parsear como JSON si es posible
            import json
            json_data = json.loads(response)
            console.print_json(json.dumps(json_data, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError):
            # Si no es JSON válido, mostrar como texto
            console.print(response)
    elif not has_table and not analysis_text:
        # Si no hay tabla ni análisis detectado, mostrar respuesta completa
        console.print(response)


@click.group()
def cli():
    """Sistema LLM para consultas a Data Warehouse."""
    pass


@cli.command()
@click.argument("question", required=True)
@click.option("--verbose", "-v", is_flag=True, help="Mostrar SQL generado y detalles")
@click.option("--explain", "-e", is_flag=True, help="Explicar qué hace el SQL antes de ejecutarlo")
@click.option("--stream", "-s", is_flag=True, help="Streaming de resultados (útil para queries grandes)")
@click.option("--limit", "-l", type=int, default=None, help="Límite de resultados")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Formato de salida")
@click.option("--export", type=click.Choice(["csv", "json", "excel"]), default=None, help="Exportar resultados a archivo")
def query(question: str, verbose: bool, explain: bool, stream: bool, limit: int | None, format: str, export: str | None):
    """
    Ejecuta una consulta en lenguaje natural sobre la base de datos.

    Ejemplo:
        llm-dw query "¿Cuál es el total de revenue por país en enero?"
    """
    try:
        console.print(f"[bold blue]Pregunta:[/bold blue] {question}\n")

        # Pre-cargar modelo de embeddings si está habilitado (evita latencia en primera query)
        try:
            from src.utils.semantic_cache import initialize_semantic_cache
            initialize_semantic_cache()
        except Exception as e:
            logger.debug(f"No se pudo pre-cargar modelo de embeddings: {e}")

        # Cargar schema
        schema = load_schema()
        logger.info("Schema cargado exitosamente")

        # Obtener engine
        try:
            engine = get_db_engine()
            logger.info("Engine de base de datos obtenido")
        except DatabaseConnectionError as e:
            console.print(f"[bold red]Error de conexión:[/bold red] {e.message}")
            sys.exit(1)

        # Crear agente
        try:
            agent = create_sql_agent(engine, schema)
            logger.info("Agente SQL creado")
        except Exception as e:
            console.print(f"[bold red]Error al crear agente:[/bold red] {str(e)}")
            logger.error(f"Error al crear agente: {e}")
            sys.exit(1)

        # Ejecutar query
        try:
            # Si explain está activado, primero generar SQL y explicarlo
            # Nota: explain no funciona bien con streaming, así que lo desactivamos temporalmente
            sql_generated = None
            if explain and not stream:
                # Ejecutar en modo verbose para obtener SQL primero (sin streaming)
                result_preview = execute_query(agent, question, return_metadata=True, stream=False)
                if isinstance(result_preview, dict):
                    sql_generated = result_preview.get("sql_generated")
                
                if sql_generated:
                    console.print("\n[bold yellow]Explicación de la Query:[/bold yellow]")
                    try:
                        explanation = explain_query(sql_generated, engine)
                        console.print(explanation)
                    except Exception as e:
                        logger.warning(f"Error al generar explicación completa: {e}")
                        # Fallback a explicación simple
                        explanation = explain_query_simple(sql_generated)
                        console.print(explanation)
                    console.print()
                else:
                    console.print("[yellow]No se pudo obtener SQL para explicar. Continuando con ejecución...[/yellow]\n")
            elif explain and stream:
                console.print("[yellow]Nota: --explain no está disponible con --stream. Ejecutando sin explicación.[/yellow]\n")
            
            # Si verbose está activado, obtener metadata (SQL generado, tiempo, etc.)
            if verbose:
                if stream:
                    # Modo streaming con display en tiempo real
                    display = _display_streaming_response(question)
                    
                    def stream_callback(chunk_info: dict):
                        """Callback para actualizar display durante streaming."""
                        if chunk_info:
                            display.update(chunk_info)
                    
                    try:
                        result = execute_query(agent, question, return_metadata=True, stream=True, stream_callback=stream_callback)
                        display.stop()
                    except Exception as e:
                        display.stop()
                        raise e
                else:
                    result = execute_query(agent, question, return_metadata=True, stream=False)
                if isinstance(result, dict):
                    response = result.get("response", "")
                    # Usar SQL de explain si está disponible, sino del resultado
                    if not sql_generated:
                        sql_generated = result.get("sql_generated")
                    execution_time = result.get("execution_time", 0)
                    
                    # Mostrar SQL generado si está disponible
                    if sql_generated:
                        console.print("\n[bold cyan]SQL Generado:[/bold cyan]")
                        syntax = Syntax(sql_generated, "sql", theme="monokai", line_numbers=False)
                        console.print(syntax)
                        console.print()
                    
                    # Mostrar tiempo de ejecución
                    console.print(f"[dim]Tiempo de ejecución: {execution_time:.2f}s[/dim]\n")
                    
                    # Mostrar respuesta formateada
                    console.print("[bold green]Respuesta:[/bold green]\n")
                    _format_query_result(response, output_format=format, sql_generated=sql_generated, question=question)
                    
                    # Exportar si se solicita
                    if export:
                        _export_results(response, sql_generated, export, question)
                    
                    # Guardar en historial
                    save_query(
                        question,
                        sql_generated,
                        response,
                        success=result.get("success", True),
                        cache_hit_type=result.get("cache_hit_type"),
                        model_used=result.get("model_used"),
                    )
                    
                    # Registrar métricas de performance
                    if sql_generated:
                        record_query_performance(
                            sql=sql_generated,
                            execution_time=execution_time,
                            success=result.get("success", True),
                        )
                else:
                    # Fallback si no se retorna dict
                    console.print("[bold green]Respuesta:[/bold green]\n")
                    _format_query_result(result, output_format=format, sql_generated=sql_generated if 'sql_generated' in locals() else None, question=question)
                    
                    # Exportar si se solicita
                    if export:
                        _export_results(result, None, export, question)
                    
                    save_query(question, None, result, success=True)
                    
                    # Registrar métricas de performance (sin SQL, métricas limitadas)
                    record_query_performance(
                        sql="",  # SQL no disponible
                        execution_time=0.0,
                        success=True,
                    )
            else:
                # Modo normal sin metadata
                if stream:
                    # Modo streaming con display en tiempo real
                    display = _display_streaming_response(question)
                    
                    def stream_callback(chunk_info: dict):
                        """Callback para actualizar display durante streaming."""
                        if chunk_info:
                            display.update(chunk_info)
                    
                    try:
                        response = execute_query(agent, question, stream=True, stream_callback=stream_callback)
                        display.stop()
                        
                        # Mostrar respuesta final formateada
                        console.print("\n[bold green]Respuesta Final:[/bold green]\n")
                        _format_query_result(response, output_format=format, sql_generated=None, question=question)
                    except Exception as e:
                        display.stop()
                        raise e
                else:
                    # Modo normal sin streaming
                    response = execute_query(agent, question, stream=False)
                    console.print("[bold green]Respuesta:[/bold green]\n")
                    _format_query_result(response, output_format=format, sql_generated=None, question=question)
                
                # Exportar si se solicita
                if export:
                    _export_results(response, None, export, question)
                
                # Guardar en historial (sin SQL porque no tenemos metadata)
                save_query(question, None, response, success=True)
                
                # Registrar métricas de performance (sin SQL, métricas limitadas)
                record_query_performance(
                    sql="",  # SQL no disponible
                    execution_time=0.0,
                    success=True,
                )

        except SQLValidationError as e:
            console.print(f"[bold red]Error de validación SQL:[/bold red] {e.message}")
            if e.details:
                if "allowed_tables" in e.details:
                    console.print(f"[yellow]Tablas permitidas:[/yellow] {', '.join(e.details['allowed_tables'])}")
                if "allowed_columns" in e.details:
                    console.print(f"[yellow]Columnas permitidas:[/yellow] {', '.join(e.details['allowed_columns'])}")
            if verbose and hasattr(e, 'sql'):
                console.print(f"\n[dim]SQL que causó el error:[/dim] {e.sql}")
            logger.error(f"Error de validación SQL: {e}")
            sys.exit(1)
        except DatabaseConnectionError as e:
            console.print(f"[bold red]Error de conexión a la base de datos:[/bold red] {e.message}")
            console.print("[yellow]Sugerencia:[/yellow] Verifica que PostgreSQL esté corriendo y que DATABASE_URL sea correcta.")
            logger.error(f"Error de conexión: {e}")
            sys.exit(1)
        except Exception as e:
            error_msg = str(e)
            console.print(f"[bold red]Error al ejecutar query:[/bold red] {error_msg}")
            
            # Guardar query fallida en historial
            save_query(question, None, error_msg, success=False)
            
            # Sugerencias basadas en el tipo de error
            if "API" in error_msg or "OpenAI" in error_msg:
                console.print("[yellow]Sugerencia:[/yellow] Verifica tu OPENAI_API_KEY en .env")
            elif "timeout" in error_msg.lower():
                console.print("[yellow]Sugerencia:[/yellow] La query tardó demasiado. Intenta con un LIMIT o verifica la query.")
            elif "tabla" in error_msg.lower() or "table" in error_msg.lower():
                console.print("[yellow]Sugerencia:[/yellow] Verifica que la tabla exista en el schema. Usa 'schema' para ver tablas disponibles.")
            
            logger.error(f"Error al ejecutar query: {e}")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operación cancelada por el usuario[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Error inesperado:[/bold red] {str(e)}")
        logger.exception("Error inesperado en comando query")
        sys.exit(1)


@cli.command()
def schema():
    """Muestra el schema de la base de datos disponible."""
    try:
        schema = load_schema()
        schema_text = get_schema_for_prompt(schema)

        console.print("[bold blue]Schema de Base de Datos:[/bold blue]\n")
        console.print(schema_text)

    except Exception as e:
        console.print(f"[bold red]Error al cargar schema:[/bold red] {str(e)}")
        logger.error(f"Error al cargar schema: {e}")
        sys.exit(1)


@cli.command()
def test_connection():
    """Prueba la conexión a la base de datos."""
    try:
        console.print("[bold blue]Probando conexión a la base de datos...[/bold blue]\n")

        if test_connection():
            console.print("[bold green]✓ Conexión exitosa[/bold green]")
            sys.exit(0)
        else:
            console.print("[bold red]✗ Error de conexión[/bold red]")
            console.print("Verifica tu configuración en .env (DATABASE_URL)")
            sys.exit(1)

    except DatabaseConnectionError as e:
        console.print(f"[bold red]Error de conexión:[/bold red] {e.message}")
        if e.details.get("database_url"):
            console.print(f"URL: {e.details['database_url']}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error inesperado:[/bold red] {str(e)}")
        logger.exception("Error inesperado en test-connection")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", type=int, default=20, help="Número de entradas a mostrar")
@click.option("--clear", is_flag=True, help="Limpiar historial completo")
def history(limit: int, clear: bool):
    """Muestra el historial de queries ejecutadas."""
    try:
        if clear:
            clear_history()
            console.print("[bold green]✓ Historial limpiado[/bold green]")
            return
        
        history_entries = load_history(limit=limit)
        
        if not history_entries:
            console.print("[yellow]No hay historial de queries[/yellow]")
            return
        
        console.print(f"[bold blue]Historial de Queries (últimas {len(history_entries)}):[/bold blue]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Fecha/Hora", style="cyan", width=20)
        table.add_column("Pregunta", style="white", width=50)
        table.add_column("Estado", style="green", width=10)
        table.add_column("SQL", style="dim", width=30)
        
        for i, entry in enumerate(history_entries, 1):
            timestamp = entry.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            question = entry.get("question", "")[:47] + "..." if len(entry.get("question", "")) > 50 else entry.get("question", "")
            success = "✓" if entry.get("success", True) else "✗"
            sql = entry.get("sql", "")
            sql_display = sql[:27] + "..." if sql and len(sql) > 30 else (sql or "-")
            
            table.add_row(
                str(i),
                timestamp,
                question,
                success,
                sql_display,
            )
        
        console.print(table)
        console.print(f"\n[dim]Usa 'history --clear' para limpiar el historial[/dim]")
    
    except Exception as e:
        console.print(f"[bold red]Error al cargar historial:[/bold red] {str(e)}")
        logger.error(f"Error en comando history: {e}")
        sys.exit(1)


@cli.command()
@click.option("--days", "-d", type=int, default=7, help="Número de días hacia atrás para analizar")
@click.option("--slow-threshold", type=float, default=5.0, help="Threshold en segundos para queries lentas")
@click.option("--clear", is_flag=True, help="Limpiar todas las métricas")
def stats(days: int, slow_threshold: float, clear: bool):
    """
    Muestra estadísticas de performance de queries.
    
    Ejemplo:
        llm-dw stats --days 30
        llm-dw stats --slow-threshold 10.0
    """
    try:
        if clear:
            clear_performance_metrics()
            console.print("[bold green]✓ Métricas de performance limpiadas[/bold green]")
            return
        
        # Obtener estadísticas generales
        stats_data = get_performance_stats(days=days)
        
        if stats_data["total_queries"] == 0:
            console.print(f"[yellow]No hay métricas de performance para los últimos {days} días[/yellow]")
            return
        
        console.print(f"[bold blue]Estadísticas de Performance (últimos {days} días):[/bold blue]\n")
        
        # Tabla de estadísticas generales
        stats_table = Table(show_header=True, header_style="bold magenta")
        stats_table.add_column("Métrica", style="cyan")
        stats_table.add_column("Valor", style="white")
        
        stats_table.add_row("Total de Queries", str(stats_data["total_queries"]))
        stats_table.add_row("Exitosas", f"{stats_data['successful_queries']} ({stats_data['success_rate']:.1f}%)")
        stats_table.add_row("Fallidas", str(stats_data["failed_queries"]))
        stats_table.add_row("Tiempo Promedio", f"{stats_data['avg_execution_time']:.2f}s")
        stats_table.add_row("Tiempo Mínimo", f"{stats_data['min_execution_time']:.2f}s")
        stats_table.add_row("Tiempo Máximo", f"{stats_data['max_execution_time']:.2f}s")
        stats_table.add_row("Queries Lentas", f"{stats_data['slow_queries_count']} (>={slow_threshold}s)")
        
        # Agregar métricas de optimización si están disponibles
        if stats_data.get('avg_tokens_total'):
            stats_table.add_row("Tokens Promedio", f"{stats_data['avg_tokens_total']:.0f}")
        if stats_data.get('cache_hit_rate'):
            stats_table.add_row("Cache Hit Rate", f"{stats_data['cache_hit_rate']:.1f}%")
        if stats_data.get('semantic_cache_hits'):
            stats_table.add_row("Semantic Cache Hits", str(stats_data['semantic_cache_hits']))
        if stats_data.get('sql_cache_hits'):
            stats_table.add_row("SQL Cache Hits", str(stats_data['sql_cache_hits']))
        
        console.print(stats_table)
        console.print()
        
        # Mostrar distribución de modelos si está disponible
        if stats_data.get('model_distribution'):
            console.print("[bold cyan]Distribución de Modelos:[/bold cyan]\n")
            model_table = Table(show_header=True, header_style="bold magenta")
            model_table.add_column("Modelo", style="cyan")
            model_table.add_column("Queries", style="white")
            model_table.add_column("Porcentaje", style="yellow")
            
            total_queries = stats_data['total_queries']
            for model, count in stats_data['model_distribution'].items():
                percentage = (count / total_queries * 100) if total_queries > 0 else 0
                model_table.add_row(model or "N/A", str(count), f"{percentage:.1f}%")
            
            console.print(model_table)
            console.print()
        
        # Queries lentas
        slow_queries = get_slow_queries(threshold_seconds=slow_threshold, limit=5) or []
        if slow_queries:
            console.print(f"[bold yellow]Top 5 Queries Lentas (>={slow_threshold}s):[/bold yellow]\n")
            slow_table = Table(show_header=True, header_style="bold magenta")
            slow_table.add_column("SQL Preview", style="white", width=60)
            slow_table.add_column("Tiempo", style="red", width=10)
            slow_table.add_column("Fecha", style="dim", width=20)
            
            # Usar set para evitar duplicados exactos
            seen_queries = set()
            for query in slow_queries:
                sql = query.get("sql", "").strip()
                if not sql:
                    continue
                
                # Crear key único basado en SQL y tiempo (para evitar duplicados exactos)
                query_key = (sql[:100], query.get("execution_time", 0))
                if query_key in seen_queries:
                    continue
                seen_queries.add(query_key)
                
                sql_preview = sql[:57] + "..." if len(sql) > 60 else sql
                time_str = f"{query.get('execution_time', 0):.2f}s"
                timestamp = query.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                slow_table.add_row(sql_preview, time_str, timestamp)
            
            if slow_table.rows:
                console.print(slow_table)
                console.print()
        
        # Queries fallidas recientes
        failed_queries = get_failed_queries(limit=5) or []
        if failed_queries:
            console.print("[bold red]Queries Fallidas Recientes:[/bold red]\n")
            failed_table = Table(show_header=True, header_style="bold magenta")
            failed_table.add_column("SQL Preview", style="white", width=60)
            failed_table.add_column("Error", style="red", width=30)
            failed_table.add_column("Fecha", style="dim", width=20)
            
            for query in failed_queries:
                sql_preview = query.get("sql", "")[:57] + "..." if len(query.get("sql", "")) > 60 else query.get("sql", "")
                error = query.get("error_message", "Unknown")[:27] + "..." if len(query.get("error_message", "")) > 30 else query.get("error_message", "Unknown")
                timestamp = query.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                failed_table.add_row(sql_preview, error, timestamp)
            
            console.print(failed_table)
            console.print()
        
        # Patrones de queries
        patterns = get_query_patterns(limit=5)
        if patterns:
            console.print("[bold cyan]Patrones de Queries Más Frecuentes:[/bold cyan]\n")
            patterns_table = Table(show_header=True, header_style="bold magenta")
            patterns_table.add_column("SQL Preview", style="white", width=50)
            patterns_table.add_column("Frecuencia", style="cyan", width=10)
            patterns_table.add_column("Tiempo Promedio", style="yellow", width=15)
            patterns_table.add_column("Éxito", style="green", width=10)
            
            for pattern in patterns:
                sql_preview = pattern.get("sql_preview", "").strip()
                if not sql_preview:
                    continue
                
                sql_preview = sql_preview[:47] + "..." if len(sql_preview) > 50 else sql_preview
                count = str(pattern.get("count", 0))
                avg_time = f"{pattern.get('avg_time', 0):.2f}s"
                success_rate = f"{pattern.get('success_count', 0)}/{pattern.get('count', 0)}"
                
                patterns_table.add_row(sql_preview, count, avg_time, success_rate)
            
            if patterns_table.rows:
                console.print(patterns_table)
    
    except Exception as e:
        console.print(f"[bold red]Error al cargar estadísticas:[/bold red] {str(e)}")
        logger.error(f"Error en comando stats: {e}")
        sys.exit(1)


@cli.command()
@click.argument("sql", required=True)
def validate_sql(sql: str):
    """
    Valida una query SQL manualmente.

    Ejemplo:
        llm-dw validate-sql "SELECT * FROM sales"
    """
    try:
        console.print(f"[bold blue]Validando SQL:[/bold blue]\n")

        # Mostrar SQL con syntax highlighting
        syntax = Syntax(sql, "sql", theme="monokai", line_numbers=False)
        console.print(syntax)
        console.print()

        # Cargar schema
        schema = load_schema()
        validator = SQLValidator(schema)

        # Validar
        try:
            validator.validate_query(sql)
            console.print("[bold green]✓ SQL válido[/bold green]")
            console.print("La query cumple con todas las validaciones de seguridad.")

            # Mostrar información adicional
            tables = validator.extract_tables(sql)
            if tables:
                console.print(f"\n[bold]Tablas detectadas:[/bold] {', '.join(tables)}")

        except SQLValidationError as e:
            console.print(f"[bold red]✗ Error de validación:[/bold red] {e.message}")
            if e.details:
                console.print(f"[yellow]Detalles:[/yellow] {json.dumps(e.details, indent=2)}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error inesperado:[/bold red] {str(e)}")
        logger.exception("Error inesperado en validate-sql")
        sys.exit(1)


if __name__ == "__main__":
    cli()
