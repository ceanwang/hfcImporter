#

__title__ = "FreeCAD SU2 library"
__author__ = "John Wang based on importCcxFrdResults.py" 

## @package importSU2Mesh
#  \ingroup FEM
#  \brief FreeCAD SU2 Reader for FEM workbench

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
    importSU2Mesh(filename)
	
# ********* module specific methods *********
def importSU2Mesh(
    filename,
    analysis=None,
    result_name_prefix=""
):
    from . import importToolsFem
    import ObjectsFem

    m = read_SU2_mesh(filename)
    result_mesh_object = None
    if len(m["Nodes"]) > 0:
        mesh = importToolsFem.make_femmesh(m)
        result_mesh_object = ObjectsFem.makeMeshResult(
            FreeCAD.ActiveDocument,
            "ResultMesh"
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
                    # if a pure SU2 file was opened no analysis and thus no parent group
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
            "Problem on SU2 file import. No nodes found in SU2 file.\n"
        )


# read a SU2 result file and extract the nodes
# displacement vectors and stress values.
def read_SU2_mesh(
    SU2_input
):
    Console.PrintMessage(
        "Read SU2 mesh from SU2 file: {}\n"
        .format(SU2_input)
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
    end_of_SU2_data_found = False
    input_continues = False
    mode_eigen_changed = False
    mode_time_changed = False

    eigenmode = 0
    eigentemp = 0
    elem = -1
    elemType = 0
    timestep = 0
    timetemp = 0
	
    SU2_file = pyopen(SU2_input, "r")
	
    #isOneZone=0

    tline=[]
    for line in SU2_file:
        aline=line.strip()	
        if len(aline)==0 or aline[0]=='%':
            continue
        else:		
            tline.append(line.strip())
		
    print ("")			
    i=0
    data = tline[i].split()
    dName=data[0]
    if dName=='NZONE=':
        NZONE= int(data[1])
    elif dName=='NDIME=':
        i=i+1
        data = tline[i].split()
        dName=data[0]
        if dName=='NZONE=':
           NZONE= int(data[1])
        else:
           NZONE=1
           i=i-2
    print ("NZONE: "+str(NZONE))
		
    memStart=0
    nodeStart=0
    for idZ in range(NZONE): # Member
        if NZONE>1:	
            i+=1
            print ("")			
            data = tline[i].split()
            dName=data[0]
            IZONE= int(data[1])
            print ("IZONE: "+str(IZONE))
		
        i+=1
        print ("")			
        data = tline[i].split()
        dName=data[0]
        NDIME= int(data[1])
        print ("NDIME: "+str(NDIME))
			
        i+=1
        print ("")			
        data = tline[i].split()
        NELEM =  int(data[1])
        numMember=NELEM
        print ("NELEM: "+str(numMember))

		
        for idM in range(numMember): # Member
            #5	5122	5109	5075	10215        
            i+=1
            #print (tline[i])
            dataNode = tline[i].split()
            elem = int(dataNode[0])
            if (elem==3):  #line
                # 3   109  110
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                elements_seg2[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1)
                continue
            elif (elem==5):  #triangle
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                #elements_seg3[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1)
                elements_tria3[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1)

            elif (elem==9): #Quadrilateral
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                elements_quad4[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1)
        		
            elif (elem==10): #Tetrahedral
                #10	17331	102263	102225	102187	36
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                elements_tetra4[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1)
				
            elif (elem==12): #Hexahedral
                #12	0	1	21	20	800	801	821	820	0
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                nd5 = int(dataNode[5])
                nd6 = int(dataNode[6])
                nd7 = int(dataNode[7])
                nd8 = int(dataNode[8])
                elements_hexa8[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1, nodeStart+nd5+1, nodeStart+nd6+1, nodeStart+nd7+1, nodeStart+nd8+1)
                continue
            elif (elem==13): #Prism
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                nd5 = int(dataNode[5])
                nd6 = int(dataNode[6])
                elements_penta6[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1, nodeStart+nd5+1, nodeStart+nd6+1)
                continue
            elif (elem==14): #Pyramid
                #10	17331	102263	102225	102187	36
                nd1 = int(dataNode[1])
                nd2 = int(dataNode[2])
                nd3 = int(dataNode[3])
                nd4 = int(dataNode[4])
                nd5 = int(dataNode[5])
                elements_tetra4[memStart+idM+1] = (nodeStart+nd1+1, nodeStart+nd2+1, nodeStart+nd3+1, nodeStart+nd4+1, nodeStart+nd5+1)
            else:
                print ("elem=")+str(elem)+" not supprot yet."			
        memStart=memStart+numMember
		
		#node 22222222222222222222222222222222222222222222222222222222222222222222
        #NPOIN= 5233
        i+=1
        data = tline[i].split()
        NPOIN =  int(data[1])
        numNode = NPOIN
        print ("NPOIN: "+str(numNode))

        for idN in range(numNode): # node
            i+=1	
	        #9.997500181200000e-01	-3.632896519016437e-05	0
            #print (tline[i])
            dataNode = tline[i].split()

            nodes_x = float(dataNode[0])
            nodes_y = float(dataNode[1])
            if NDIME==2:		
                nodes_z = 0.
            else:
                nodes_z = float(dataNode[2])	
            nodes[nodeStart+idN+1] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)
            #print (str(nodes_x))
        nodeStart=nodeStart+numNode

        #NMARK= 5
        #MARKER_TAG= IN
        #MARKER_ELEMS= 35    
        i+=1
        if i<len(tline):
            print (tline[i])
            data = tline[i].split()
            dName =  data[0]
            if dName=='NMARK=':
                NMark =  int(data[1])
                print ("NMark: "+str(NMark))
			
                for idMark in range(NMark): # node
                    print (str(idMark))
			 
                    i+=1	
                    data = tline[i].split()
                    print (tline[i])
			
                    i+=1	
                    data = tline[i].split()
                    MARKER_ELEMS=int(data[1])
                    print ("MARKER_ELEMS: "+str(MARKER_ELEMS))
			
                    for jd in range(MARKER_ELEMS): # node
                        i+=1	
                        #dataNode = tline[i].split()
            else:
                i=i-1	
			
            #NPERIODIC= 1
            #break
		
    # close SU2 file if loop over all lines is finished
    SU2_file.close()

    if not inout_nodes:
        if results:
            if "mflow" in results[0] or "npressure" in results[0]:
                Console.PrintError(
                    "We have mflow or npressure, but no inout_nodes file.\n"
                )
    if not nodes:
        Console.PrintError("FEM: No nodes found in SU2 file.\n")

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
