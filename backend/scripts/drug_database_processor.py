import os
import sqlite3
import json
import pandas as pd
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class DrugData:
    """Data class to hold comprehensive drug information"""
    drug_id: int
    drug_name: str
    drug_url: str
    components: List[Dict[str, Any]]
    effects: List[Dict[str, Any]]
    chembl_mappings: List[Dict[str, Any]]
    targets: List[Dict[str, Any]]
    genes: List[Dict[str, Any]]

class DrugDatabaseProcessor:
    """
    Processes the drug database and creates comprehensive drug profiles
    suitable for vector embedding generation.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
    def connect_to_database(self):
        """Establish connection to SQLite database"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def get_drug_components(self, drug_id: int) -> List[Dict[str, Any]]:
        """Get all components for a drug"""
        query = """
        SELECT 
            dc.drug_component_id,
            dc.drug_component_name,
            cm.compound_pref_name,
            cm.compound_chembl_id,
            cm.molecule_type,
            cm.indication_class,
            cm.full_mapping,
            cm.mapping_synonym
        FROM drug_component dc
        LEFT JOIN chembl_mapping cm ON dc.drug_component_id = cm.drug_component_id
        WHERE dc.drug_id = ?
        """
        
        cursor = self.connection.cursor()
        cursor.execute(query, (drug_id,))
        rows = cursor.fetchall()
        
        components = []
        for row in rows:
            component = {
                'component_name': row['drug_component_name'],
                'chembl_id': row['compound_chembl_id'],
                'preferred_name': row['compound_pref_name'],
                'molecule_type': row['molecule_type'],
                'indication_class': row['indication_class'],
                'full_mapping': bool(row['full_mapping']) if row['full_mapping'] is not None else None,
                'mapping_synonym': row['mapping_synonym']
            }
            components.append(component)
        
        return components
    
    def get_drug_effects(self, drug_id: int) -> List[Dict[str, Any]]:
        """Get all effects for a drug"""
        query = """
        SELECT 
            de.drug_effect_type,
            de.drug_effect_freq,
            de.drug_effect_name,
            de.drug_class_effect,
            de.drug_class,
            dem.drug_effect_mapping_cui,
            dem.drug_effect_mapping_term
        FROM drug_effect de
        LEFT JOIN drug_effect_mapping dem ON de.drug_effect_id = dem.drug_effect_id
        WHERE de.drug_id = ?
        """
        
        cursor = self.connection.cursor()
        cursor.execute(query, (drug_id,))
        rows = cursor.fetchall()
        
        effects = []
        for row in rows:
            effect = {
                'effect_type': row['drug_effect_type'],
                'frequency': row['drug_effect_freq'],
                'effect_name': row['drug_effect_name'],
                'class_effect': bool(row['drug_class_effect']) if row['drug_class_effect'] is not None else False,
                'drug_class': row['drug_class'],
                'cui_code': row['drug_effect_mapping_cui'],
                'mapping_term': row['drug_effect_mapping_term']
            }
            effects.append(effect)
        
        return effects
    
    def get_drug_targets(self, drug_id: int) -> List[Dict[str, Any]]:
        """Get all target information for a drug"""
        query = """
        SELECT DISTINCT
            ctc.target_chembl_id,
            ctc.target_type,
            ctc.target_pref_name,
            ctc.organism,
            ctc.action_type,
            ctc.mechanism_of_action,
            ctc.uniprot_accession,
            ctc.uniprot_description,
            eg.ensembl_gene_id,
            eg.chr_name,
            eg.start_pos,
            eg.end_pos,
            eg.strand,
            eg.ensembl_description
        FROM drug_component dc
        JOIN chembl_mapping cm ON dc.drug_component_id = cm.drug_component_id
        JOIN chembl_target_components ctc ON cm.chembl_mapping_id = ctc.chembl_mapping_id
        LEFT JOIN ensembl_genes eg ON ctc.uniprot_accession = eg.uniprot_accession
        WHERE dc.drug_id = ?
        """
        
        cursor = self.connection.cursor()
        cursor.execute(query, (drug_id,))
        rows = cursor.fetchall()
        
        targets = []
        for row in rows:
            target = {
                'target_chembl_id': row['target_chembl_id'],
                'target_type': row['target_type'],
                'target_name': row['target_pref_name'],
                'organism': row['organism'],
                'action_type': row['action_type'],
                'mechanism_of_action': row['mechanism_of_action'],
                'uniprot_accession': row['uniprot_accession'],
                'uniprot_description': row['uniprot_description'],
                'ensembl_gene_id': row['ensembl_gene_id'],
                'chromosome': row['chr_name'],
                'gene_start': row['start_pos'],
                'gene_end': row['end_pos'],
                'strand': row['strand'],
                'gene_description': row['ensembl_description']
            }
            targets.append(target)
        
        return targets
    
    def get_comprehensive_drug_data(self, drug_id: int) -> DrugData:
        """Get complete drug information"""
        # Get basic drug info
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM drug WHERE drug_id = ?", (drug_id,))
        drug_row = cursor.fetchone()
        
        if not drug_row:
            raise ValueError(f"Drug with ID {drug_id} not found")
        
        # Get related data
        components = self.get_drug_components(drug_id)
        effects = self.get_drug_effects(drug_id)
        targets = self.get_drug_targets(drug_id)
        
        return DrugData(
            drug_id=drug_row['drug_id'],
            drug_name=drug_row['drug_name'],
            drug_url=drug_row['drug_url'],
            components=components,
            effects=effects,
            chembl_mappings=[],  # Already included in components
            targets=targets,
            genes=[]  # Already included in targets
        )
    
    def create_drug_text_representation(self, drug_data: DrugData) -> str:
        """
        Create a comprehensive text representation of drug data
        optimized for embedding generation
        """
        text_parts = []
        
        # Basic drug information
        text_parts.append(f"Drug Name: {drug_data.drug_name}")
        text_parts.append(f"Drug ID: {drug_data.drug_id}")
        
        # Components/Active ingredients
        if drug_data.components:
            components_text = "Active Components: "
            component_names = []
            for comp in drug_data.components:
                comp_text = comp['component_name']
                if comp['preferred_name'] and comp['preferred_name'] != comp['component_name']:
                    comp_text += f" ({comp['preferred_name']})"
                if comp['molecule_type']:
                    comp_text += f" [Type: {comp['molecule_type']}]"
                component_names.append(comp_text)
            components_text += ", ".join(component_names)
            text_parts.append(components_text)
        
        # Indications
        indications = [effect for effect in drug_data.effects if effect['effect_type'] == 'indication']
        if indications:
            indication_text = "Medical Indications: "
            indication_names = [ind['effect_name'] for ind in indications]
            indication_text += "; ".join(indication_names)
            text_parts.append(indication_text)
        
        # Side effects
        side_effects = [effect for effect in drug_data.effects if effect['effect_type'] == 'side_effect']
        if side_effects:
            # Group by frequency
            freq_groups = {}
            for effect in side_effects:
                freq = effect['frequency']
                if freq not in freq_groups:
                    freq_groups[freq] = []
                freq_groups[freq].append(effect['effect_name'])
            
            for freq, effects in freq_groups.items():
                if freq and freq != 'not_known':
                    text_parts.append(f"Side Effects ({freq}): {'; '.join(effects)}")
                else:
                    text_parts.append(f"Side Effects: {'; '.join(effects)}")
        
        # Drug classes
        drug_classes = list(set([effect['drug_class'] for effect in drug_data.effects 
                               if effect['drug_class']]))
        if drug_classes:
            text_parts.append(f"Drug Classes: {', '.join(drug_classes)}")
        
        # Mechanisms of action and targets
        if drug_data.targets:
            mechanisms = list(set([target['mechanism_of_action'] for target in drug_data.targets 
                                 if target['mechanism_of_action']]))
            if mechanisms:
                text_parts.append(f"Mechanisms of Action: {'; '.join(mechanisms)}")
            
            target_names = list(set([target['target_name'] for target in drug_data.targets 
                                   if target['target_name']]))
            if target_names:
                text_parts.append(f"Molecular Targets: {'; '.join(target_names[:10])}")  # Limit for space
            
            target_types = list(set([target['target_type'] for target in drug_data.targets 
                                   if target['target_type']]))
            if target_types:
                text_parts.append(f"Target Types: {', '.join(target_types)}")
        
        return "\n".join(text_parts)
    
    def create_drug_json_representation(self, drug_data: DrugData) -> Dict[str, Any]:
        """Create a structured JSON representation of drug data"""
        return {
            'drug_id': drug_data.drug_id,
            'drug_name': drug_data.drug_name,
            'drug_url': drug_data.drug_url,
            'components': drug_data.components,
            'effects': {
                'indications': [e for e in drug_data.effects if e['effect_type'] == 'indication'],
                'side_effects': [e for e in drug_data.effects if e['effect_type'] == 'side_effect'],
                'other_effects': [e for e in drug_data.effects if e['effect_type'] not in ['indication', 'side_effect']]
            },
            'targets': drug_data.targets,
            'drug_classes': list(set([e['drug_class'] for e in drug_data.effects if e['drug_class']])),
            'mechanisms_of_action': list(set([t['mechanism_of_action'] for t in drug_data.targets if t['mechanism_of_action']]))
        }
    
    def process_all_drugs_to_csv(self, output_file: str = 'comprehensive_drug_data.csv'):
        """Process all drugs and save to CSV"""
        logger.info("Starting to process all drugs...")
        
        # Get all drug IDs
        cursor = self.connection.cursor()
        cursor.execute("SELECT drug_id FROM drug ORDER BY drug_id")
        drug_ids = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(drug_ids)} drugs to process")
        
        processed_drugs = []
        failed_drugs = []
        
        for i, drug_id in enumerate(drug_ids, 1):
            try:
                if i % 100 == 0:
                    logger.info(f"Processed {i}/{len(drug_ids)} drugs")
                
                drug_data = self.get_comprehensive_drug_data(drug_id)
                text_representation = self.create_drug_text_representation(drug_data)
                json_representation = self.create_drug_json_representation(drug_data)
                
                processed_drugs.append({
                    'drug_id': drug_data.drug_id,
                    'drug_name': drug_data.drug_name,
                    'drug_url': drug_data.drug_url,
                    'text_content': text_representation,
                    'json_data': json.dumps(json_representation, ensure_ascii=False),
                    'component_count': len(drug_data.components),
                    'effect_count': len(drug_data.effects),
                    'target_count': len(drug_data.targets)
                })
                
            except Exception as e:
                logger.error(f"Failed to process drug {drug_id}: {e}")
                failed_drugs.append(drug_id)
                continue
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(processed_drugs)
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        logger.info(f"Successfully processed {len(processed_drugs)} drugs")
        logger.info(f"Failed to process {len(failed_drugs)} drugs: {failed_drugs}")
        logger.info(f"Data saved to: {output_file}")
        
        return output_file, len(processed_drugs), failed_drugs
    
    def get_database_statistics(self):
        """Get statistics about the database"""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Count records in each table
        tables = ['drug', 'drug_component', 'drug_effect', 'drug_effect_mapping', 
                 'chembl_mapping', 'chembl_target_components', 'ensembl_genes']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[f'{table}_count'] = cursor.fetchone()[0]
        
        # Drugs with components
        cursor.execute("""
            SELECT COUNT(DISTINCT drug_id) FROM drug_component
        """)
        stats['drugs_with_components'] = cursor.fetchone()[0]
        
        # Drugs with effects
        cursor.execute("""
            SELECT COUNT(DISTINCT drug_id) FROM drug_effect
        """)
        stats['drugs_with_effects'] = cursor.fetchone()[0]
        
        # Drugs with targets
        cursor.execute("""
            SELECT COUNT(DISTINCT dc.drug_id) 
            FROM drug_component dc
            JOIN chembl_mapping cm ON dc.drug_component_id = cm.drug_component_id
            JOIN chembl_target_components ctc ON cm.chembl_mapping_id = ctc.chembl_mapping_id
        """)
        stats['drugs_with_targets'] = cursor.fetchone()[0]
        
        return stats

def main():
    """Main function to process the drug database"""
    # Resolve DB path from environment or default to backend/data/bnf_20210409.db
    default_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'bnf_20210409.db')
    db_path = os.getenv('BNF_DB_PATH', default_db_path)
    logger.info(f"Using drug database path: {db_path}")
    
    processor = DrugDatabaseProcessor(db_path)
    
    try:
        processor.connect_to_database()
        
        # Get database statistics
        logger.info("Getting database statistics...")
        stats = processor.get_database_statistics()
        for key, value in stats.items():
            logger.info(f"{key}: {value}")
        
        # Process all drugs
        output_file, processed_count, failed_ids = processor.process_all_drugs_to_csv()
        
        logger.info("Processing complete!")
        logger.info(f"Output file: {output_file}")
        logger.info(f"Successfully processed: {processed_count} drugs")
        
        if failed_ids:
            logger.warning(f"Failed drug IDs: {failed_ids}")
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise
    
    finally:
        processor.close_connection()

if __name__ == "__main__":
    main()
