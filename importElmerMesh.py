#

__title__ = "hfc mesh library"
__author__ = "John Wang based on importCcxFrdResults.py" 

## @package importElmerMesh
#  \ingroup FEM
#  \brief FreeCAD Elmer Reader for FEM workbench

import FreeCAD
from FreeCAD import Console
import os

def moveon(fp):	
	while 1:
		line = fp.readline().strip()
		if len(line)==0 or line[0]=='#':
			continue
		else:
			return line


# ********* generic FreeCAD import and export methods *********
if open.__module__ == "__builtin__":
    # because we'll redefine open below (Python2)
    pyopen = open
elif open.__module__ == "io":
    # because we'll redefine open below (Python3)
    pyopen = open


def open(filename):
    "called when freecad opens a file"
    docname = os.path.splitext(os.path.basename(filename))[0]
    insert(filename, docname)


def insert(
    filename,
    docname
):
    "called when freecad wants to import a file"
    try:
        doc = FreeCAD.getDocument(docname)
    except NameError:
        doc = FreeCAD.newDocument(docname)
    FreeCAD.ActiveDocument = doc
    importElmerMesh(filename)
	
# ********* module specific methods *********
def importElmerMesh(
    filename,
    analysis=None,
    result_name_prefix=""
):
    from . import importToolsFem
    import ObjectsFem

    m = read_Elmer_mesh(filename,0)
    result_mesh_object = None
    if len(m["Nodes"]) > 0:
        mesh = importToolsFem.make_femmesh(m)
        result_mesh_object = ObjectsFem.makeMeshResult(
            FreeCAD.ActiveDocument,
            "Mesh"
        )
        result_mesh_object.FemMesh = mesh
        res_mesh_is_compacted = False
        nodenumbers_for_compacted_mesh = []

        number_of_increments = len(m["Results"])
        Console.PrintLog(
            "Increments: " + str(number_of_increments) + "\n"
        )
        if len(m["Results"]) > 0:
            for result_set in m["Results"]:
                if "number" in result_set:
                    eigenmode_number = result_set["number"]
                else:
                    eigenmode_number = 0
                step_time = result_set["time"]
                step_time = round(step_time, 2)
                if eigenmode_number > 0:
                    results_name = (
                        "{}Mode{}_Results"
                        .format(result_name_prefix, eigenmode_number)
                    )
                elif number_of_increments > 1:
                    results_name = (
                        "{}Time{}_Results"
                        .format(result_name_prefix, step_time)
                    )
                else:
                    results_name = (
                        "{}Results"
                        .format(result_name_prefix)
                    )

                res_obj = ObjectsFem.makeResultMechanical(FreeCAD.ActiveDocument, results_name)
                res_obj.Mesh = result_mesh_object
                res_obj = importToolsFem.fill_femresult_mechanical(res_obj, result_set)
                if analysis:
                    analysis.addObject(res_obj)

                # complementary result object calculations
                import femresult.resulttools as restools
                import femtools.femutils as femutils
                if not res_obj.MassFlowRate:
                    if res_mesh_is_compacted is False:
                        # first result set, compact FemMesh and NodeNumbers
                        res_obj = restools.compact_result(res_obj)
                        res_mesh_is_compacted = True
                        nodenumbers_for_compacted_mesh = res_obj.NodeNumbers
                    else:
                        # all other result sets, do not compact FemMesh, only set NodeNumbers
                        res_obj.NodeNumbers = nodenumbers_for_compacted_mesh

                # fill DisplacementLengths
                res_obj = restools.add_disp_apps(res_obj)
                # fill StressValues
                res_obj = restools.add_von_mises(res_obj)
                if res_obj.getParentGroup():
                    has_reinforced_mat = False
                    for obj in res_obj.getParentGroup().Group:
                        if obj.isDerivedFrom("App::MaterialObjectPython") \
                                and femutils.is_of_type(obj, "Fem::MaterialReinforced"):
                            has_reinforced_mat = True
                            restools.add_principal_stress_reinforced(res_obj)
                            break
                    if has_reinforced_mat is False:
                        # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                        res_obj = restools.add_principal_stress_std(res_obj)
                else:
                    # if a pure Elmer file was opened no analysis and thus no parent group
                    # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                    res_obj = restools.add_principal_stress_std(res_obj)
                # fill Stats
                res_obj = restools.fill_femresult_stats(res_obj)
                return res_obj


        else:
            error_message = (
                "We have nodes only.\n"
            )
            Console.PrintMessage(error_message)
            if analysis:
                analysis.addObject(result_mesh_object)

        if FreeCAD.GuiUp:
            if analysis:
                import FemGui
                FemGui.setActiveAnalysis(analysis)
            FreeCAD.ActiveDocument.recompute()

    else:
        Console.PrintError(
            "Problem on Elmer file import. No nodes found in Elmer file.\n"
        )


# read a Elmer result file and extract the nodes
# displacement vectors and stress values.
def read_Elmer_mesh(
    Elmer_input,
	iBND
):
    Console.PrintMessage(
        "Read Elmer mesh from Elmer file: {}\n"
        .format(Elmer_input)
    )
	
    nodes = {}
    elements_hexa8 = {}
    elements_penta6 = {}
    elements_tetra4 = {}
    elements_tetra10 = {}
    elements_penta15 = {}
    elements_hexa20 = {}
    elements_tria3 = {}
    elements_tria6 = {}
    elements_quad4 = {}
    elements_quad8 = {}
    elements_seg2 = {}
    elements_seg3 = {}
    results = []
    mode_results = {}
    mode_results["number"] = float("NaN")
    mode_results["time"] = float("NaN")
    mode_disp = {}
    mode_stress = {}
    mode_strain = {}
    mode_peeq = {}
    mode_temp = {}
    mode_massflow = {}
    mode_networkpressure = {}

    nodes_found = False
    elements_found = False
    mode_time_found = False
    mode_disp_found = False
    mode_stress_found = False
    mode_strain_found = False
    mode_peeq_found = False
    mode_temp_found = False
    mode_massflow_found = False
    mode_networkpressure_found = False
    end_of_section_found = False
    end_of_Elmer_data_found = False
    input_continues = False
    mode_eigen_changed = False
    mode_time_changed = False

    eigenmode = 0
    eigentemp = 0
    elem = -1
    elemType = 0
    timestep = 0
    timetemp = 0
	
    print ('Input = '+Elmer_input)
	
	#get path
    data=Elmer_input.split("/")
    n=len(data)
    path=""
    for i in range(n-1):
        path=path+data[i]+"/"
	
    print ('path = '+path)
	#1111111111111111111111111111111111111111111111111111
    Elmer_header_file = pyopen(path+"mesh.header","r")
	
    line = Elmer_header_file.readline().strip()
    data=line.split()
    numNode=int(data[0])
    numMember=int(data[1])
    numBC=int(data[2])
	
    print ("numNode = "+str(numNode))
    print ("numMember = "+str(numMember))
	
    #line = Elmer_header_file.readline().strip()
    #NDIME=data[0]

    Elmer_header_file.close()

	#node 22222222222222222222222222222222222222222222222222222222222222222222
    Elmer_node_file = pyopen(path+"mesh.nodes","r")
	#NPOIN= 52
    tline=[]
    for line in Elmer_node_file:
        aline=line.strip()	
        if len(aline)==0 or aline[0]=='%':
            continue
        else:		
            tline.append(line.strip())
		
    Elmer_node_file.close()
	
    for idN in range(numNode): # node
        #1 -1 0 1 0
        dataNode = tline[idN].split()

        nodes_x = float(dataNode[2])
        nodes_y = float(dataNode[3])
        nodes_z = float(dataNode[4])	
        nodes[idN+1] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)
		#print (str(nodes_x))


		
	#member 333333333333333333333333333
    if iBND==1:
        Elmer_member_file = pyopen(path+"mesh.boundary","r")
    else:
        Elmer_member_file = pyopen(path+"mesh.elements","r")
		
    tline=[]
    for line in Elmer_member_file:
        aline=line.strip()	
        if len(aline)==0 or aline[0]=='%':
            continue
        else:		
            tline.append(line.strip())
			
    Elmer_member_file.close()
	
    nodeStart=0
    memStart=0
	
    if iBND==1:
        numMember=numBC	
	
    for idM in range(numMember): # Member
        #print (tline[i])
        #1 1 408 1 21 23 3 14 22 15 2
		#
        dataNode = tline[idM].split()
        if iBND==1:
            elem = int(dataNode[4])
        else:
            elem = int(dataNode[2])
		
        if (elem==202 or elem==203 ):  #quadratic line
			# 3   109  110
            if iBND==1:
                nd1 = int(dataNode[5])
                nd2 = int(dataNode[6])
                elements_seg2[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2)
            else:
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                elements_seg2[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2)
        elif (elem==303 or elem==306 ):  #triangle
            if iBND==1:
				#nd1 = int(dataNode[5])
				#nd2 = int(dataNode[6])
				#nd3 = int(dataNode[7])
				#elements_tria3[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3)
                continue
            else:
                nd1 = int(dataNode[5])
                nd2 = int(dataNode[6])
                nd3 = int(dataNode[7])
                elements_tria3[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3)

        elif (elem==404 or elem==408): #Quadrilateral
		
            if iBND==1:
				#nd1 = int(dataNode[3])
				#nd2 = int(dataNode[4])
				#nd3 = int(dataNode[5])
				#nd4 = int(dataNode[6])
				#print (str(nd1))
				#elements_quad4[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3, nodeStart+nd4)
                continue
            else:
                nd1 = int(dataNode[3])
                nd2 = int(dataNode[4])
                nd3 = int(dataNode[5])
                nd4 = int(dataNode[6])
                #print (str(nd1))
                elements_quad4[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3, nodeStart+nd4)
			
			
        elif (elem==510): #Tetrahedral
            if iBND==1:
                continue
            else:
				#10	17331	102263	102225	102187	36
                nd1 = int(dataNode[3])
                nd2 = int(dataNode[4])
                nd3 = int(dataNode[5])
                nd4 = int(dataNode[6])
                elements_tetra4[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3, nodeStart+nd4)
			
        elif (elem==808): #Hexahedral
            if iBND==1:
                continue
            else:
				#12	0	1	21	20	800	801	821	820	0
                nd1 = int(dataNode[3])
                nd2 = int(dataNode[4])
                nd3 = int(dataNode[5])
                nd4 = int(dataNode[6])
                nd5 = int(dataNode[7])
                nd6 = int(dataNode[8])
                nd7 = int(dataNode[9])
                nd8 = int(dataNode[10])
                elements_hexa8[memStart+idM+1] = (nodeStart+nd1, nodeStart+nd2, nodeStart+nd3, nodeStart+nd4, nodeStart+nd5, nodeStart+nd6, nodeStart+nd7, nodeStart+nd8)
        elif (elem==13): #Prism
            continue
        elif (elem==14): #Pyramid
            if iBND==1:
                continue
            else:
				#10	17331	102263	102225	102187	36
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                nd5 = int(dataNode[5])
                elements_tetra4[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1, nodeStart+nd5+1)
        else:
            print ("elem=")+str(elem)+" not supprot yet."			
	

    if not nodes:
        Console.PrintError("FEM: No nodes found in Elmer file.\n")

    return {
        "Nodes": nodes,
        "Seg2Elem": elements_seg2,
        "Seg3Elem": elements_seg3,
        "Tria3Elem": elements_tria3,
        "Tria6Elem": elements_tria6,
        "Quad4Elem": elements_quad4,
        "Quad8Elem": elements_quad8,
        "Tetra4Elem": elements_tetra4,
        "Tetra10Elem": elements_tetra10,
        "Hexa8Elem": elements_hexa8,
        "Hexa20Elem": elements_hexa20,
        "Penta6Elem": elements_penta6,
        "Penta15Elem": elements_penta15,
        "Results": results
    }
