import sqlite3
import json
import os
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class DrugInfo:
    """Comprehensive drug information compiled from multiple tables"""
    drug_id: int
    drug_name: str
    drug_url: str
    components: List[str]
    indications: List[str]
    side_effects: List[Dict[str, str]]
    contraindications: List[str]
    interactions: List[str]
    targets: List[Dict[str, str]]
    genes: List[Dict[str, str]]
    chembl_info: List[Dict[str, str]]

class DrugDatabaseProcessor:
    """Processes the drug database to create meaningful text chunks for vector embeddings"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def extract_all_drug_data(self) -> List[DrugInfo]:
        """Extract and compile comprehensive drug information from all tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all drugs
            cursor.execute("SELECT drug_id, drug_name, drug_url FROM drug ORDER BY drug_name")
            drugs = cursor.fetchall()
            
            drug_info_list = []
            
            for drug_id, drug_name, drug_url in drugs:
                drug_info = self._compile_drug_info(cursor, drug_id, drug_name, drug_url)
                drug_info_list.append(drug_info)
                
            return drug_info_list
            
        finally:
            conn.close()
    
    def _compile_drug_info(self, cursor, drug_id: int, drug_name: str, drug_url: str) -> DrugInfo:
        """Compile comprehensive information for a single drug"""
        
        # Get drug components
        components = self._get_drug_components(cursor, drug_id)
        
        # Get drug effects (indications, side effects, contraindications)
        indications, side_effects, contraindications, interactions = self._get_drug_effects(cursor, drug_id)
        
        # Get ChEMBL and target information
        chembl_info, targets, genes = self._get_drug_targets_and_genes(cursor, drug_id)
        
        return DrugInfo(
            drug_id=drug_id,
            drug_name=drug_name,
            drug_url=drug_url,
            components=components,
            indications=indications,
            side_effects=side_effects,
            contraindications=contraindications,
            interactions=interactions,
            targets=targets,
            genes=genes,
            chembl_info=chembl_info
        )
    
    def _get_drug_components(self, cursor, drug_id: int) -> List[str]:
        """Get all components for a drug"""
        cursor.execute("""
            SELECT drug_component_name 
            FROM drug_component 
            WHERE drug_id = ?
        """, (drug_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_drug_effects(self, cursor, drug_id: int) -> tuple:
        """Get all effects for a drug, categorized by type"""
        cursor.execute("""
            SELECT drug_effect_type, drug_effect_freq, drug_effect_name, drug_class_effect, drug_class
            FROM drug_effect 
            WHERE drug_id = ?
        """, (drug_id,))
        
        effects = cursor.fetchall()
        
        indications = []
        side_effects = []
        contraindications = []
        interactions = []
        
        for effect_type, freq, name, class_effect, drug_class in effects:
            if effect_type == 'indication':
                indications.append(name)
            elif effect_type == 'side_effect':
                side_effects.append({
                    'name': name,
                    'frequency': freq or 'unknown',
                    'class_effect': bool(class_effect),
                    'drug_class': drug_class or 'specific'
                })
            elif effect_type == 'contraindication':
                contraindications.append(name)
            elif effect_type == 'interaction':
                interactions.append(name)
        
        return indications, side_effects, contraindications, interactions
    
    def _get_drug_targets_and_genes(self, cursor, drug_id: int) -> tuple:
        """Get ChEMBL mapping, target, and gene information for a drug"""
        # Get ChEMBL mappings
        cursor.execute("""
            SELECT cm.compound_pref_name, cm.compound_chembl_id, cm.molecule_type, 
                   cm.indication_class, cm.mapping_synonym
            FROM drug_component dc
            JOIN chembl_mapping cm ON dc.drug_component_id = cm.drug_component_id
            WHERE dc.drug_id = ?
        """, (drug_id,))
        
        chembl_data = cursor.fetchall()
        chembl_info = []
        chembl_mapping_ids = []
        
        for compound_name, chembl_id, mol_type, indication_class, synonym in chembl_data:
            chembl_info.append({
                'compound_name': compound_name,
                'chembl_id': chembl_id,
                'molecule_type': mol_type or 'unknown',
                'indication_class': indication_class or 'unknown',
                'synonym': synonym or compound_name
            })
            
            # Get the mapping ID for target information
            cursor.execute("""
                SELECT chembl_mapping_id FROM chembl_mapping cm
                JOIN drug_component dc ON cm.drug_component_id = dc.drug_component_id
                WHERE dc.drug_id = ? AND cm.compound_chembl_id = ?
            """, (drug_id, chembl_id))
            mapping_ids = cursor.fetchall()
            chembl_mapping_ids.extend([mid[0] for mid in mapping_ids])
        
        # Get target information
        targets = []
        genes = []
        
        if chembl_mapping_ids:
            placeholders = ','.join('?' * len(chembl_mapping_ids))
            cursor.execute(f"""
                SELECT DISTINCT ctc.mechanism_of_action, ctc.target_pref_name, ctc.target_type,
                       ctc.organism, ctc.action_type, ctc.uniprot_accession, ctc.uniprot_description
                FROM chembl_target_components ctc
                WHERE ctc.chembl_mapping_id IN ({placeholders})
            """, chembl_mapping_ids)
            
            target_data = cursor.fetchall()
            
            for moa, target_name, target_type, organism, action_type, uniprot_acc, uniprot_desc in target_data:
                targets.append({
                    'mechanism_of_action': moa or 'unknown',
                    'target_name': target_name or 'unknown',
                    'target_type': target_type or 'unknown',
                    'organism': organism or 'unknown',
                    'action_type': action_type or 'unknown'
                })
                
                # Get gene information if uniprot accession exists
                if uniprot_acc:
                    cursor.execute("""
                        SELECT ensembl_gene_id, chr_name, start_pos, end_pos, 
                               strand, ensembl_description
                        FROM ensembl_genes
                        WHERE uniprot_accession = ?
                    """, (uniprot_acc,))
                    
                    gene_data = cursor.fetchall()
                    for gene_id, chr_name, start_pos, end_pos, strand, description in gene_data:
                        genes.append({
                            'ensembl_gene_id': gene_id,
                            'chromosome': chr_name,
                            'start_position': start_pos,
                            'end_position': end_pos,
                            'strand': strand,
                            'description': description or 'unknown',
                            'uniprot_accession': uniprot_acc,
                            'uniprot_description': uniprot_desc or 'unknown'
                        })
        
        return chembl_info, targets, genes
    
    def create_text_chunks(self, drug_info_list: List[DrugInfo]) -> List[Dict[str, Any]]:
        """Convert drug information into meaningful text chunks for embeddings"""
        chunks = []
        
        for drug_info in drug_info_list:
            # Create main drug overview chunk
            main_chunk = self._create_drug_overview_chunk(drug_info)
            chunks.append(main_chunk)
            
            # Create detailed pharmacology chunk if target/gene info exists
            if drug_info.targets or drug_info.genes:
                pharma_chunk = self._create_pharmacology_chunk(drug_info)
                chunks.append(pharma_chunk)
            
            # Create side effects chunk if substantial side effect data
            if len(drug_info.side_effects) > 3:
                effects_chunk = self._create_side_effects_chunk(drug_info)
                chunks.append(effects_chunk)
            
            # Create interaction/contraindication chunk if data exists
            if drug_info.contraindications or drug_info.interactions:
                safety_chunk = self._create_safety_chunk(drug_info)
                chunks.append(safety_chunk)
        
        return chunks
    
    def _create_drug_overview_chunk(self, drug_info: DrugInfo) -> Dict[str, Any]:
        """Create a comprehensive drug overview text chunk"""
        text_parts = [
            f"Drug: {drug_info.drug_name}",
            f"Drug ID: {drug_info.drug_id}"
        ]
        
        if drug_info.components:
            if len(drug_info.components) == 1:
                text_parts.append(f"Active ingredient: {drug_info.components[0]}")
            else:
                text_parts.append(f"Active ingredients: {', '.join(drug_info.components)}")
        
        if drug_info.indications:
            text_parts.append(f"Indications: {'; '.join(drug_info.indications)}")
        
        if drug_info.chembl_info:
            chembl_parts = []
            for chembl in drug_info.chembl_info:
                chembl_part = f"{chembl['compound_name']} (ChEMBL ID: {chembl['chembl_id']}, Type: {chembl['molecule_type']}"
                if chembl['indication_class'] != 'unknown':
                    chembl_part += f", Class: {chembl['indication_class']}"
                chembl_part += ")"
                chembl_parts.append(chembl_part)
            text_parts.append(f"Chemical information: {'; '.join(chembl_parts)}")
        
        # Add common side effects (up to 5 most frequent)
        if drug_info.side_effects:
            common_effects = [se['name'] for se in drug_info.side_effects[:5]]
            text_parts.append(f"Common side effects: {', '.join(common_effects)}")
        
        text = "\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": {
                "source": "drug_database",
                "drug_name": drug_info.drug_name,
                "drug_id": drug_info.drug_id,
                "chunk_type": "drug_overview",
                "drug_url": drug_info.drug_url,
                "components": drug_info.components
            }
        }
    
    def _create_pharmacology_chunk(self, drug_info: DrugInfo) -> Dict[str, Any]:
        """Create a detailed pharmacology and mechanism chunk"""
        text_parts = [
            f"Pharmacology of {drug_info.drug_name}",
            f"Drug ID: {drug_info.drug_id}"
        ]
        
        if drug_info.targets:
            text_parts.append("Molecular targets and mechanisms:")
            for target in drug_info.targets:
                target_text = f"- Target: {target['target_name']} ({target['target_type']})"
                if target['mechanism_of_action'] != 'unknown':
                    target_text += f", Mechanism: {target['mechanism_of_action']}"
                if target['action_type'] != 'unknown':
                    target_text += f", Action: {target['action_type']}"
                if target['organism'] != 'unknown':
                    target_text += f", Organism: {target['organism']}"
                text_parts.append(target_text)
        
        if drug_info.genes:
            text_parts.append("Associated genes:")
            for gene in drug_info.genes:
                gene_text = f"- Gene: {gene['ensembl_gene_id']} (Chromosome {gene['chromosome']}:{gene['start_position']}-{gene['end_position']})"
                if gene['description'] != 'unknown':
                    gene_text += f", Function: {gene['description']}"
                if gene['uniprot_description'] != 'unknown':
                    gene_text += f", Protein: {gene['uniprot_description']}"
                text_parts.append(gene_text)
        
        text = "\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": {
                "source": "drug_database",
                "drug_name": drug_info.drug_name,
                "drug_id": drug_info.drug_id,
                "chunk_type": "pharmacology",
                "drug_url": drug_info.drug_url,
                "targets_count": len(drug_info.targets),
                "genes_count": len(drug_info.genes)
            }
        }
    
    def _create_side_effects_chunk(self, drug_info: DrugInfo) -> Dict[str, Any]:
        """Create a detailed side effects chunk"""
        text_parts = [
            f"Side Effects Profile of {drug_info.drug_name}",
            f"Drug ID: {drug_info.drug_id}"
        ]
        
        # Group side effects by frequency
        freq_groups = {}
        for se in drug_info.side_effects:
            freq = se['frequency']
            if freq not in freq_groups:
                freq_groups[freq] = []
            freq_groups[freq].append(se)
        
        # Order frequencies by clinical importance
        freq_order = ['very_common', 'common', 'uncommon', 'rare', 'very_rare', 'not_known', 'unknown']
        
        for freq in freq_order:
            if freq in freq_groups:
                text_parts.append(f"{freq.replace('_', ' ').title()} side effects:")
                for se in freq_groups[freq]:
                    se_text = f"- {se['name']}"
                    if se['class_effect'] and se.get('drug_class'):
                        se_text += f" (class effect for {se['drug_class']})"
                    text_parts.append(se_text)
        
        text = "\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": {
                "source": "drug_database",
                "drug_name": drug_info.drug_name,
                "drug_id": drug_info.drug_id,
                "chunk_type": "side_effects",
                "drug_url": drug_info.drug_url,
                "total_side_effects": len(drug_info.side_effects)
            }
        }
    
    def _create_safety_chunk(self, drug_info: DrugInfo) -> Dict[str, Any]:
        """Create a safety, contraindications, and interactions chunk"""
        text_parts = [
            f"Safety Information for {drug_info.drug_name}",
            f"Drug ID: {drug_info.drug_id}"
        ]
        
        if drug_info.contraindications:
            text_parts.append("Contraindications:")
            for contra in drug_info.contraindications:
                text_parts.append(f"- {contra}")
        
        if drug_info.interactions:
            text_parts.append("Drug interactions:")
            for interaction in drug_info.interactions:
                text_parts.append(f"- {interaction}")
        
        text = "\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": {
                "source": "drug_database",
                "drug_name": drug_info.drug_name,
                "drug_id": drug_info.drug_id,
                "chunk_type": "safety",
                "drug_url": drug_info.drug_url,
                "contraindications_count": len(drug_info.contraindications),
                "interactions_count": len(drug_info.interactions)
            }
        }
    
    def process_database_to_json(self, output_file: str) -> str:
        """Process the entire database and save as JSON for embedding"""
        print("Extracting drug data from database...")
        drug_info_list = self.extract_all_drug_data()
        print(f"Extracted data for {len(drug_info_list)} drugs")
        
        print("Creating text chunks...")
        chunks = self.create_text_chunks(drug_info_list)
        print(f"Created {len(chunks)} text chunks")
        
        # Prepare data in the same format as the existing pipeline
        formatted_data = []
        for chunk in chunks:
            formatted_data.append({
                "text": chunk["text"],
                "metadata": chunk["metadata"]
                # Note: embeddings will be generated later by the vectorstore system
            })
        
        print(f"Saving {len(formatted_data)} chunks to {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        return output_file 
        