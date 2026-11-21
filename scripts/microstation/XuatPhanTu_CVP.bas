Attribute VB_Name = "XuatPhanTu_CVP"
' =============================================================================
' CadastralValidatorPro - Macro VBA xuất phần tử DGN ra JSON (cvp.dgn_exchange/1)
' Chạy TRONG MicroStation V8i: Utilities > Macro > Project Manager > Load .bas
' rồi chạy XuatPhanTuJSON. Macro CHỈ ĐỌC model hiện hành, không sửa bản vẽ.
' TRẠNG THÁI: NOT_TESTED trên máy thật - cần nghiệm thu với DC1..DC10.dgn.
' Văn bản tiếng Việt được ghi dạng \uXXXX nên không phụ thuộc mã trang.
' Cung tròn/ellipse/B-spline: chưa rời rạc hóa, chỉ đếm (báo trong "stats").
' =============================================================================
Option Explicit

Private nOut As Long
Private nSkip As Long

Private Function JsonStr(ByVal s As String) As String
    Dim i As Long, c As Long, r As String
    r = Chr(34)
    For i = 1 To Len(s)
        c = AscW(Mid$(s, i, 1))
        If c < 0 Then c = c + 65536
        Select Case c
            Case 34: r = r & "\" & Chr(34)
            Case 92: r = r & "\\"
            Case 10: r = r & "\n"
            Case 13: r = r & "\r"
            Case 9: r = r & "\t"
            Case 32 To 126: r = r & ChrW(c)
            Case Else: r = r & "\u" & Right$("0000" & Hex$(c), 4)
        End Select
    Next i
    JsonStr = r & Chr(34)
End Function

Private Function Num(ByVal d As Double) As String
    Num = Replace(Format$(d, "0.000000"), ",", ".")
End Function

Private Function PtJson(p As Point3d) As String
    PtJson = "[" & Num(p.X) & "," & Num(p.Y) & "]"
End Function

Private Function TypeName2(ByVal t As Long) As String
    Select Case t
        Case msdElementTypeCellHeader: TypeName2 = "cell"
        Case msdElementTypeLine: TypeName2 = "line"
        Case msdElementTypeLineString: TypeName2 = "linestring"
        Case msdElementTypeShape: TypeName2 = "shape"
        Case msdElementTypeTextNode: TypeName2 = "textnode"
        Case msdElementTypeComplexString: TypeName2 = "complex_string"
        Case msdElementTypeComplexShape: TypeName2 = "complex_shape"
        Case msdElementTypeText: TypeName2 = "text"
        Case Else: TypeName2 = ""
    End Select
End Function

Private Function ElemJson(el As Element) As String
    Dim t As String, s As String, v() As Point3d, i As Long
    Dim en As ElementEnumerator, kids As String
    t = TypeName2(el.Type)
    If t = "" Then
        nSkip = nSkip + 1
        ElemJson = ""
        Exit Function
    End If
    s = "{""id"":" & JsonStr(DLongToString(el.ID)) & ",""type"":""" & t & """,""level"":"
    If el.Level Is Nothing Then s = s & "0" Else s = s & CStr(el.Level.Number)
    Select Case el.Type
        Case msdElementTypeLine, msdElementTypeLineString, msdElementTypeShape
            v = el.AsVertexList.GetVertices
            s = s & ",""coords"":["
            For i = LBound(v) To UBound(v)
                If i > LBound(v) Then s = s & ","
                s = s & PtJson(v(i))
            Next i
            s = s & "]"
            If el.Type = msdElementTypeShape Then s = s & ",""closed"":true"
        Case msdElementTypeText
            s = s & ",""text"":" & JsonStr(el.AsTextElement.Text) & ",""origin"":" & PtJson(el.AsTextElement.Origin)
        Case msdElementTypeTextNode, msdElementTypeCellHeader, msdElementTypeComplexString, msdElementTypeComplexShape
            If el.Type = msdElementTypeTextNode Then
                Set en = el.AsTextNodeElement.GetSubElements
            ElseIf el.Type = msdElementTypeCellHeader Then
                s = s & ",""cell_name"":" & JsonStr(el.AsCellElement.Name) & ",""origin"":" & PtJson(el.AsCellElement.Origin)
                Set en = el.AsCellElement.GetSubElements
            Else
                Set en = el.AsComplexElement.GetSubElements
                If el.Type = msdElementTypeComplexShape Then s = s & ",""closed"":true"
            End If
            kids = ""
            Do While en.MoveNext
                Dim cj As String
                cj = ElemJson(en.Current)
                If cj <> "" Then
                    If kids <> "" Then kids = kids & ","
                    kids = kids & cj
                End If
            Loop
            s = s & ",""children"":[" & kids & "]"
    End Select
    ElemJson = s & "}"
End Function

Public Sub XuatPhanTuJSON()
    Dim ee As ElementEnumerator, out As String, j As String, fn As String
    Dim stm As Object
    nOut = 0: nSkip = 0
    fn = ActiveDesignFile.FullName & ".cvp.json"
    Set ee = ActiveModelReference.Scan
    out = ""
    Do While ee.MoveNext
        j = ElemJson(ee.Current)
        If j <> "" Then
            If nOut > 0 Then out = out & "," & vbLf
            out = out & j
            nOut = nOut + 1
        End If
    Loop
    out = "{""schema"":""cvp.dgn_exchange/1"",""source"":{""path"":" & JsonStr(ActiveDesignFile.FullName) & _
          ",""dgn_version"":""V8"",""reader"":""microstation_vba"",""is_synthetic"":false}," & _
          """sheet"":{""sheet_id"":" & JsonStr(ActiveDesignFile.Name) & "},""units"":{""master"":""m""}," & _
          """stats"":{""exported"":" & nOut & ",""skipped_unsupported"":" & nSkip & "}," & _
          """elements"":[" & out & "]}"
    Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2: stm.Charset = "us-ascii": stm.Open
    stm.WriteText out
    stm.SaveToFile fn, 2
    stm.Close
    ShowMessage "CVP: da xuat " & nOut & " phan tu (bo qua " & nSkip & ") -> " & fn
End Sub
