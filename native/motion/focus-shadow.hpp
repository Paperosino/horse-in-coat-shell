// A Gaussian falloff around a rounded rectangle, drawn in the current working
// framebuffer. The shadow's extent is clipped before fragment evaluation.
#pragma once
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Shader.hpp>
#include <hyprutils/utils/ScopeGuard.hpp>

namespace hics::motion {
class FocusShadow {
  public:
    bool draw(CBox box, Vector2D size, double scale, double elevation, CHyprColor accent) {
        if (!shader()) return false;
        GLint viewport[4], scissor[4], vao, arrayBuffer;
        GLboolean mask[4];
        glGetIntegerv(GL_VIEWPORT,viewport); glGetIntegerv(GL_SCISSOR_BOX,scissor);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&vao); glGetIntegerv(GL_ARRAY_BUFFER_BINDING,&arrayBuffer);
        glGetBooleanv(GL_COLOR_WRITEMASK,mask);
        const bool blend=glIsEnabled(GL_BLEND), stencil=glIsEnabled(GL_STENCIL_TEST), clipping=glIsEnabled(GL_SCISSOR_TEST);
        auto* renderer=g_pHyprRenderer.get();
        Hyprutils::Utils::CScopeGuard restore([&] {
            renderer->setViewport(viewport[0],viewport[1],viewport[2],viewport[3]); renderer->blend(blend);
            Render::GL::g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST,stencil);
            Render::GL::g_pHyprOpenGL->setCapStatus(GL_SCISSOR_TEST,clipping);
            glScissor(scissor[0],scissor[1],scissor[2],scissor[3]); glColorMask(mask[0],mask[1],mask[2],mask[3]);
            glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,arrayBuffer);
        });
        const double sigma=(5.0+13.0*elevation)*scale, margin=std::ceil(4*sigma+12*scale);
        const int left=std::max(0,static_cast<int>(std::floor(box.x-margin)));
        const int right=std::min(static_cast<int>(size.x),static_cast<int>(std::ceil(box.x+box.w+margin)));
        const int top=std::max(0,static_cast<int>(std::floor(box.y-margin)));
        const int bottom=std::min(static_cast<int>(size.y),static_cast<int>(std::ceil(box.y+box.h+margin)));
        if(right<=left || bottom<=top)return false;
        renderer->setViewport(0,0,size.x,size.y);renderer->blend(true);
        Render::GL::g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST,false);
        Render::GL::g_pHyprOpenGL->setCapStatus(GL_SCISSOR_TEST,true);
        glScissor(left,size.y-bottom,right-left,bottom-top);glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
        Render::GL::g_pHyprOpenGL->useShader(m_shader);
        glUniform2f(m_size,size.x,size.y);
        glUniform4f(m_box,box.x,size.y-box.y-box.h,box.w,box.h);
        glUniform4f(m_params,12*scale,sigma,(3+7*elevation)*scale,elevation);
        glUniform3f(m_accent,accent.r,accent.g,accent.b);
        glBindVertexArray(m_shader->getUniformLocation(SHADER_SHADER_VAO));
        glDrawArrays(GL_TRIANGLE_STRIP,0,4);
        return glGetError()==GL_NO_ERROR;
    }
  private:
    bool shader() {
        if(m_shader)return true;
        if(m_attempted)return false;
        m_attempted=true;auto value=makeShared<CShader>();
        const std::string vertex=R"GLSL(#version 300 es
precision highp float;
in vec2 pos;
void main(){gl_Position=vec4(pos*2.0-1.0,0.0,1.0);}
)GLSL";
        const std::string fragment=R"GLSL(#version 300 es
precision highp float;
uniform vec2 screenSize;
uniform vec4 box;
uniform vec4 params;
uniform vec3 accent;
out vec4 result;
float roundedDistance(vec2 p,vec2 center,vec2 halfSize,float r){
 vec2 q=abs(p-center)-(halfSize-vec2(r));
 return length(max(q,vec2(0.0)))+min(max(q.x,q.y),0.0)-r;
}
void main(){
 vec2 center=box.xy+box.zw*.5;
 float sigma=max(params.y,.1);
 float d=max(0.0,roundedDistance(gl_FragCoord.xy,center-vec2(0.0,params.z),box.zw*.5,params.x));
 float shadow=(.28+.18*params.w)*exp(-.5*d*d/(sigma*sigma));
 float h=max(0.0,roundedDistance(gl_FragCoord.xy,center,box.zw*.5,params.x)-5.0);
 float halo=.11*params.w*exp(-.5*h*h/(sigma*sigma));
 float a=clamp(shadow+halo*(1.0-shadow),0.0,1.0);
 result=vec4(accent*halo*(1.0-shadow),a);
}
)GLSL";
        if(!value->createProgram(vertex,fragment,true,true))return false;
        m_size=glGetUniformLocation(value->program(),"screenSize");m_box=glGetUniformLocation(value->program(),"box");
        m_params=glGetUniformLocation(value->program(),"params");m_accent=glGetUniformLocation(value->program(),"accent");
        m_shader=value;return true;
    }
    SP<CShader> m_shader;
    bool m_attempted=false;
    GLint m_size=-1,m_box=-1,m_params=-1,m_accent=-1;
};
}
